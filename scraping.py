import os
import time
import json
import requests
import pandas as pd
from itertools import combinations
from concurrent.futures import ThreadPoolExecutor, as_completed

# ==============================================================================
# 1. CONFIGURAÇÕES E AUTENTICAÇÃO
# ==============================================================================
# No terminal (Linux), rode antes: export GITHUB_TOKEN="seu_token_aqui"
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "COLE_SEU_TOKEN_AQUI")

PASTA_SAIDA = "dataset"
ARQUIVO_CACHE_ESTRELAS = f"{PASTA_SAIDA}/cache_estrelas_usuarios.json"
os.makedirs(PASTA_SAIDA, exist_ok=True)

HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28"
}
if GITHUB_TOKEN and GITHUB_TOKEN != "COLE_SEU_TOKEN_AQUI":
    HEADERS["Authorization"] = f"Bearer {GITHUB_TOKEN}"
else:
    print("[AVISO] Rodando sem GITHUB_TOKEN (limite restrito a 60 req/h). Recomenda-se usar Token!")

# Repositórios-alvo divididos por ecossistema (inspirado no target 0 e 1 do SNAP)
# Grupo 0: Ecossistema PlayStation (Kyty + KytyPS5 + ShadPS4)
# Grupo 1: Ecossistema Nintendo (CitronNEO + Dolphin + Azahar)
REPOSITORIOS = {
    "KytyPS5/KytyPS5": 0,                # Emulador PS5
    "shadps4-emu/shadPS4": 0,            # Emulador PS4
    "InoriRus/Kyty": 0,                  # Core p/ Emulador PS4/5
    "azahar-emu/azahar": 1,              # Emulador 3DS
    "citron-neo/emulator": 1,            # Emulador Switch
    "dolphin-emu/dolphin": 1,            # Emulador Wii/GameCube
}

MAX_PAGINAS_POR_ENDPOINT = 10
MIN_ESTRELAS_DADAS = 10  # Filtro inspirado no dataset SNAP (mínimo de 10 repos favoritados)

# ==============================================================================
# 2. FUNÇÕES AUXILIARES DE REQUISIÇÃO E LIMPEZA (BOTS + >= 10 ESTRELAS)
# ==============================================================================
def requisitar_github(url, params=None):
    """Faz requisição GET tratando rate-limit automaticamente."""
    while True:
        try:
            resp = requests.get(url, headers=HEADERS, params=params, timeout=15)
        except requests.RequestException as e:
            print(f"[!] Erro de conexão ({e}). Tentando novamente em 5s...")
            time.sleep(5)
            continue

        if resp.status_code == 200:
            return resp.json()
        elif resp.status_code in (403, 429):
            reset_time = int(resp.headers.get("X-RateLimit-Reset", time.time() + 60))
            espera = max(reset_time - int(time.time()), 5)
            print(f"[!] Rate limit atingido. Aguardando {espera}s...")
            time.sleep(espera)
        elif resp.status_code == 404:
            return []
        else:
            print(f"[!] Erro {resp.status_code} em {url}: {resp.text[:100]}")
            return []

def eh_usuario_humano(user_obj):
    """
    ETAPA DE LIMPEZA 1:
    Remove objetos vazios, contas deletadas ('ghost') e bots automatizados.
    """
    if not user_obj or not isinstance(user_obj, dict):
        return False
    login = user_obj.get("login", "")
    tipo = user_obj.get("type", "User")
    if not login or tipo == "Bot":
        return False
    if login.lower().endswith("[bot]") or login.lower() in {"ghost", "dependabot", "github-actions"}:
        return False
    return True

def verificar_minimo_estrelas(username, min_estrelas=MIN_ESTRELAS_DADAS):
    """
    ETAPA DE LIMPEZA 2 (Inspirada no SNAP musae-github):
    Verifica se o desenvolvedor possui pelo menos `min_estrelas` repositórios
    favoritados (starred) na conta. Pede apenas 1 página de tamanho `min_estrelas`.
    """
    url = f"https://api.github.com/users/{username}/starred"
    dados = requisitar_github(url, params={"per_page": min_estrelas, "page": 1})
    return isinstance(dados, list) and len(dados) >= min_estrelas

def filtrar_usuarios_ativos(lista_usernames, min_estrelas=MIN_ESTRELAS_DADAS):
    """
    Valida a lista de usuários únicos usando cache persistente em disco
    e threads para acelerar a consulta na API do GitHub.
    """
    cache = {}
    if os.path.exists(ARQUIVO_CACHE_ESTRELAS):
        with open(ARQUIVO_CACHE_ESTRELAS, "r") as f:
            cache = json.load(f)

    faltam_consultar = [u for u in lista_usernames if u not in cache]
    print(f"\n[*] Validando filtro de >= {min_estrelas} estrelas para {len(lista_usernames)} usuários únicos...")
    print(f"    -> {len(lista_usernames) - len(faltam_consultar)} já estavam no cache local.")
    print(f"    -> {len(faltam_consultar)} serão consultados agora na API do GitHub.")

    if faltam_consultar:
        concluidos = 0
        # 6 workers simultâneos para ser rápido sem engatilhar secondary rate-limit
        with ThreadPoolExecutor(max_workers=6) as executor:
            futuros = {
                executor.submit(verificar_minimo_estrelas, user, min_estrelas): user
                for user in faltam_consultar
            }
            for futuro in as_completed(futuros):
                user = futuros[futuro]
                cache[user] = futuro.result()
                concluidos += 1
                if concluidos % 50 == 0 or concluidos == len(faltam_consultar):
                    print(f"    -> Progresso: {concluidos}/{len(faltam_consultar)} perfis verificados...")
                    with open(ARQUIVO_CACHE_ESTRELAS, "w") as f:
                        json.dump(cache, f)

        with open(ARQUIVO_CACHE_ESTRELAS, "w") as f:
            json.dump(cache, f)

    usuarios_aprovados = {u for u in lista_usernames if cache.get(u, False)}
    removidos = len(lista_usernames) - len(usuarios_aprovados)
    print(f"    -> Filtro concluído: {len(usuarios_aprovados)} aprovados | {removidos} removidos (< {min_estrelas} estrelas).")
    return usuarios_aprovados

# ==============================================================================
# 3. COLETA DE PARTICIPANTES DOS REPOSITÓRIOS (REDE BIPARTIDA)
# ==============================================================================
def coletar_usuarios_repositorio(repo_full_name, max_paginas=5):
    """
    Coleta desenvolvedores que interagiram com o repositório via:
    1. Commits (Contributors)
    2. Pull Requests (PRs abertos/fechados)
    3. Issues técnicas (Issues abertas/fechadas)
    """
    interacoes_dev = {}  # {username: {'peso': int, 'tipos': set()}}

    def registrar(user_obj, tipo_interacao, peso=1):
        if eh_usuario_humano(user_obj):
            login = user_obj["login"]
            if login not in interacoes_dev:
                interacoes_dev[login] = {"peso": 0, "tipos": set()}
            interacoes_dev[login]["peso"] += peso
            interacoes_dev[login]["tipos"].add(tipo_interacao)

    print(f"\n[*] Coletando dados do repositório: {repo_full_name}...")

    # A) Contributors (Commits diretos)
    for pag in range(1, max_paginas + 1):
        dados = requisitar_github(
            f"https://api.github.com/repos/{repo_full_name}/contributors",
            params={"per_page": 100, "page": pag}
        )
        if not dados:
            break
        for item in dados:
            contribs = int(item.get("contributions", 1))
            registrar(item, "contributor", peso=contribs)
        if len(dados) < 100:
            break

    # B) Pull Requests (Código submetido)
    for pag in range(1, max_paginas + 1):
        dados = requisitar_github(
            f"https://api.github.com/repos/{repo_full_name}/pulls",
            params={"state": "all", "per_page": 100, "page": pag}
        )
        if not dados:
            break
        for pr in dados:
            registrar(pr.get("user"), "pull_request", peso=2)
        if len(dados) < 100:
            break

    # C) Issues (Relatos de bugs, compatibilidade e discussões técnicas)
    for pag in range(1, max_paginas + 1):
        dados = requisitar_github(
            f"https://api.github.com/repos/{repo_full_name}/issues",
            params={"state": "all", "per_page": 100, "page": pag}
        )
        if not dados:
            break
        for issue in dados:
            if "pull_request" not in issue:
                registrar(issue.get("user"), "issue", peso=1)
        if len(dados) < 100:
            break

    print(f"    -> {len(interacoes_dev)} candidatos humanos encontrados em {repo_full_name}.")
    return interacoes_dev

# ==============================================================================
# 4. EXECUÇÃO DA COLETA, FILTRAGEM E CONSTRUÇÃO DOS ARQUIVOS
# ==============================================================================
def construir_dataset_emuladores():
    coleta_bruta_por_repo = {}
    todos_candidatos = set()

    # Passo 1: Varrer repositórios e reunir candidatos únicos
    for repo in REPOSITORIOS.keys():
        participantes = coletar_usuarios_repositorio(repo, max_paginas=MAX_PAGINAS_POR_ENDPOINT)
        coleta_bruta_por_repo[repo] = participantes
        todos_candidatos.update(participantes.keys())

    # Passo 2: Aplicar filtro SNAP (apenas usuários com >= 10 repositórios favoritados)
    usuarios_ativos = filtrar_usuarios_ativos( sorted(todos_candidatos), min_estrelas=MIN_ESTRELAS_DADAS)

    registros_bipartidos = []
    devs_repos = {}  # {username: {repo: {'peso': int, 'tipos': set()}}}

    for repo, ecossistema_label in REPOSITORIOS.items():
        for username, info in coleta_bruta_por_repo[repo].items():
            if username not in usuarios_ativos:
                continue  # Descarta perfis com menos de 10 estrelas dadas
            registros_bipartidos.append({
                "username": username,
                "repo": repo,
                "ecossistema": ecossistema_label,
                "peso": info["peso"],
                "tipos_interacao": "|".join(sorted(info["tipos"]))
            })
            if username not in devs_repos:
                devs_repos[username] = {}
            devs_repos[username][repo] = info

    # Passo 3: Mapear cada desenvolvedor aprovado para um ID numérico (0 a N-1)
    usuarios_ordenados = sorted(devs_repos.keys())
    user_to_id = {u: idx for idx, u in enumerate(usuarios_ordenados)}

    # Salvar arestas bipartidas (Semana 6: Dev <-> Repositório)
    bipartite_df = pd.DataFrame(registros_bipartidos)
    bipartite_df["dev_id"] = bipartite_df["username"].map(user_to_id)
    bipartite_df.to_csv(f"{PASTA_SAIDA}/emu_bipartite_edges.csv", index=False)

    # Passo 4: Criar tabela de nós (emu_git_target.csv) e dicionário de features (emu_git_features.json)
    vocab_features = {}
    def obter_id_feature(token_str):
        if token_str not in vocab_features:
            vocab_features[token_str] = len(vocab_features)
        return vocab_features[token_str]

    linhas_target = []
    features_json = {}

    for username, dev_id in user_to_id.items():
        repos_do_dev = devs_repos[username]
        pontos_eco = {0: 0, 1: 0}
        lista_feats = []

        for r, info in repos_do_dev.items():
            eco = REPOSITORIOS[r]
            pontos_eco[eco] += info["peso"]
            lista_feats.append(obter_id_feature(f"repo:{r}"))
            lista_feats.append(obter_id_feature(f"eco:{eco}"))
            for t in info["tipos"]:
                lista_feats.append(obter_id_feature(f"role:{t}"))
                lista_feats.append(obter_id_feature(f"repo_role:{r}:{t}"))

        target_binario = 1 if pontos_eco[1] >= pontos_eco[0] else 0
        atua_multiplos_projetos = 1 if len(repos_do_dev) > 1 else 0

        if atua_multiplos_projetos:
            lista_feats.append(obter_id_feature("status:multi_repo_developer"))

        linhas_target.append({
            "id": dev_id,
            "name": username,
            "ml_target": target_binario,
            "multi_repo": atua_multiplos_projetos,
            "num_repos": len(repos_do_dev),
            "total_interacoes": sum(info["peso"] for info in repos_do_dev.values())
        })

        features_json[str(dev_id)] = sorted(set(lista_feats))

    nodes_df = pd.DataFrame(linhas_target)
    nodes_df.to_csv(f"{PASTA_SAIDA}/emu_git_target.csv", index=False)

    with open(f"{PASTA_SAIDA}/emu_git_features.json", "w") as f:
        json.dump(features_json, f)

    # Passo 5: Construir a lista de arestas entre desenvolvedores (emu_git_edges.csv)
    arestas_coocorrencia = {}
    for repo in REPOSITORIOS.keys():
        devs_no_repo = [
            user_to_id[u] for u, r_dict in devs_repos.items() if repo in r_dict
        ]
        for u_id, v_id in combinations(sorted(devs_no_repo), 2):
            par = (u_id, v_id)
            arestas_coocorrencia[par] = arestas_coocorrencia.get(par, 0) + 1

    edges_df = pd.DataFrame(
        [{"id_1": u, "id_2": v, "weight": w} for (u, v), w in arestas_coocorrencia.items()]
    )
    edges_df.to_csv(f"{PASTA_SAIDA}/emu_git_edges.csv", index=False)

    print("\n" + "=" * 55)
    print("COLETA E LIMPEZA CONCLUÍDAS COM SUCESSO!")
    print(f"Candidatos humanos antes do filtro de estrelas: {len(todos_candidatos)}")
    print(f"Desenvolvedores ativos (>= {MIN_ESTRELAS_DADAS} estrelas): {len(nodes_df)}")
    print(f"Desenvolvedores em múltiplos projetos (Pontes): {nodes_df['multi_repo'].sum()}")
    print(f"Total de Arestas Bipartidas (Dev <-> Repo): {len(bipartite_df)}")
    print(f"Total de Arestas Projetadas (Dev <-> Dev): {len(edges_df)}")
    print("=" * 55)

if __name__ == "__main__":
    construir_dataset_emuladores()
