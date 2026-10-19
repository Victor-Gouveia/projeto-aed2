# Topologia e Sobreposição de Desenvolvedores em Projetos de Emulação

## Integrantes
Victor de Alcantara Gouveia

## Vídeo
https://youtu.be/uXkwqetClAc

## Problema e pergunta
O desenvolvimento de emuladores de videogames exige conhecimentos avançados de baixo nível (engenharia reversa, compiladores JIT e APIs gráficas como Vulkan/DirectX em C++). Olhar para os repositórios de forma isolada não revela como o conhecimento técnico circula entre diferentes comunidades. 

Este projeto investiga dois grandes ecossistemas — **PlayStation** (`KytyPS5`, `shadPS4` e `Kyty`) e **Nintendo** (`citron-neo`, `dolphin` e `azahar`) — guiado pela seguinte pergunta central:
> *"Há sobreposição de desenvolvedores entre projetos de emulação e, em caso afirmativo, como ela é estruturada e quais os principais contribuidores e projetos que atuam como ponte?"*

## Dados (fonte, como obter, limpeza)
* **Fonte e Coleta:** Dados extraídos via API REST do GitHub (`scraping.py`), mapeando participações técnicas (*commits*, *pull requests* e *issues*) em até $10$ páginas por *endpoint* (limite de $1.000$ registros por categoria para capturar a comunidade ativa recente).
* **Limpeza e Filtros:**
  1. **Remoção de contas automatizadas e inválidas:** Exclusão de bots (`dependabot`, `github-actions`, sufixos `[bot]`) e contas deletadas (`ghost`).
  2. **Filtro de engajamento mínimo (inspirado no SNAP *musae-github*):** Retenção apenas de usuários humanos com pelo menos $10$ repositórios favoritados (*starred*) na conta, eliminando perfis descartáveis.
  3. **Remoção de interações passivas:** *Stars* e *forks* nos emuladores não foram contabilizados.
* **Resultado da Coleta:** $1.166$ desenvolvedores ativos validados e $6$ repositórios analisados.

## Modelagem (nó, aresta, peso, direção, o que ficou de fora)
Todas as redes foram modeladas como **grafos não-dirigidos e ponderados**:

1. **Rede Bipartida ($B$: Desenvolvedor $\leftrightarrow$ Emulador):**
   * **Nós:** Conjunto $U$ de desenvolvedores ($1.166$) e conjunto $V$ de repositórios ($6$).
   * **Arestas e Pesos:** Afiliação técnica do desenvolvedor ao projeto, ponderada pela intensidade de participação (peso $1$ por *commit* ou *issue* e peso $2$ por *pull request*).
2. **Projeção de Desenvolvedores ($G_{\text{bruto}}$, $G_{\text{esqueleto}}$ e $G_{\text{pontes}}$: Dev $\leftrightarrow$ Dev):**
   * **Nós e Arestas:** Desenvolvedores conectados se contribuíram em pelo menos um emulador em comum, com peso $w$ igual ao número de emuladores compartilhados.
   * **Filtragem de Artefatos:** Para eliminar as cliques artificiais de projetos únicos na projeção bruta ($G_{\text{bruto}}$, $w \ge 1$), aplicou-se um corte de limiar ($w \ge 2$) gerando o esqueleto da rede ($G_{\text{esqueleto}}$) e a subrede exclusiva de desenvolvedores-ponte ($G_{\text{pontes}}$, com $157$ nós).
3. **Projeção dos Emuladores ($G_{\text{repos}}$: Emulador $\leftrightarrow$ Emulador):**
   * **Nós e Arestas:** Os $6$ projetos conectados pela quantidade bruta de desenvolvedores em comum e normalizados pelo **Índice de Jaccard** ($J = \frac{|A \cap B|}{|A \cup B|}$).
* **O que ficou de fora:** Interações sociais passivas (*stars*/*forks*), histórico temporal (*timestamps* das arestas) e grafos dirigidos de revisão direta de comentários.

## Conteúdo do curso utilizado

| semana | conceitos | onde aparece | para que serviu |
| --- | --- | --- | --- |
| **2** | **Tipos de grafo** (Não-dirigido e Ponderado), **Atributos de nós e arestas**, **Grau, Grau Médio e Densidade**, **Subredes** (`subgraph`) | `ProjetoAED2.ipynb`, cél. 2, 3, 4, 6 e 8 (`grafico_projetada_bruta.jpg`, `grafico_bipartida.jpg`, `grafico_devs-ponte.jpg`) | Modelar relações simétricas de co-atuação (`G`, `G_bruto`) e intensidade de contribuição (`B`), enriquecer nós com metadados de ecossistema/interação, comparar métricas estruturais (evidenciando o artefato de clique na projeção bruta) e isolar a subrede `G_pontes` ($w \ge 2$).|
| **3** | **Núcleo e Periferia**, **Efeito da amostragem / janela de coleta na estrutura** | `ProjetoAED2.ipynb`, cél. 3 (Seção 2.3) e análise de camadas (`graficos_kshell_camadas.png`) | Mapear a hierarquia topológica em `G_pontes` (separando colaboradores periféricos do núcleo coeso) e avaliar criticamente o impacto do limite de paginação da API do GitHub (10 páginas/endpoint) e dos filtros de ruído (`bots`, `< 5 stars`) na rede.|
| **4** | **Componentes e Pontes estruturais**, **Centralidade de Intermediação** (*Betweenness Centrality*), **Centralidade de Vetor Próprio** (*Eigenvector Centrality*) | `ProjetoAED2.ipynb`, cél. 3, 4 e seção de centralidades (`grafico_devs-ponte.jpg`, `grafico_centralidade.png`) | Identificar subcomunidades isoladas e o papel estrutural dos nós, contrastando desenvolvedores que atuam como pontes globais entre os ecossistemas PlayStation e Nintendo (`raphaelthegreat`, `oltolm`) com hubs locais do núcleo denso (`KAMiKAZOW`).|
| **5** | ***k-core*, *k-shell* e *Core Number***, ***Onion Layers*** (Descascamento por camadas) | `ProjetoAED2.ipynb`, seção de decomposição em núcleos (`graficos_kshell_camadas.png`) | Decompor `G_pontes` em cascas de conectividade ($k_{\max} = 101$) e refinar a ordem de descascamento interno (camadas 1 a 8), revelando a forte concentração da comunidade Nintendo nas camadas mais internas e densas.|
| **6** | **Redes Bipartidas e Projeção Unipartida**, **Co-ocorrência e Similaridade de Jaccard**, **Esqueleto por Limiar** (*Thresholding*) | `ProjetoAED2.ipynb`, cél. 2, 3, 4, 6 e 8 (`grafico_bipartida.jpg`, `grafico_devs-ponte.jpg`) | Modelar a afiliação direta Dev $\leftrightarrow$ Repo (`B`), projetar as redes unipartidas (`G_bruto` e `G_repos`), medir a afinidade proporcional entre emuladores corrigindo o viés de tamanho (Jaccard) e podar arestas fracas ($w \ge 2$ em `G_esqueleto`) para eliminar cliques artificiais.|

## Como executar

### 1. Pré-requisitos
Instale as dependências necessárias em um ambiente Python 3:
```bash
pip install -r requirements.txt
```
ou:
```bash
pip install networkx pandas numpy matplotlib requests
```

### 2. Coleta e Tratamento dos Dados (`scraping.py`)
Os dados já tratados encontram-se na pasta `dataset/`. Caso deseje refazer a coleta diretamente da API do GitHub:
```bash
export GITHUB_TOKEN="seu_token_do_github"
python scraping.py
```
Alternativamente, é possível alterar manualmente a chave de API no código.

O script irá consultar a API, filtrar bots e contas inativas, e gerar os arquivos `emu_bipartite_edges.csv`, `emu_git_edges.csv`, `emu_git_target.csv` e `emu_git_features.json` dentro de `dataset/`.

### 3. Execução da Análise e Geração das Figuras
Você pode reproduzir toda a modelagem, métricas estruturais, centralidades, decomposição $k$-core e visualizações de duas maneiras:
* **Via Jupyter Notebook (Interativo):** Abra e execute sequencialmente as células do arquivo `.ipynb` presente no repositório.
* **Via Script Python (Automático):** Execute o script `projeto.py`, que consolida todo o pipeline do Notebook de forma automatizada e salva todos os gráficos gerados no diretório `figuras/`:
  ```bash
  python projeto.py
  ```

## Resultados
* **Assimetria Modular entre Ecossistemas:** O ecossistema Nintendo forma uma comunidade fortemente integrada (destaque para a sinergia entre `azahar` e `citron-neo`, com $120$ devs em comum e Jaccard $J = 0,251$), enquanto a comunidade PlayStation é mais fragmentada.
* **Eficácia do Esqueleto por Limiar ($w \ge 2$):** A filtragem reduziu $95,8\%$ das arestas infladas por cliques de repositório único (de $185.320$ em $G_{\text{bruto}}$ para $7.870$ em $G_{\text{esqueleto}}$), isolando o núcleo real de colaboração múltipla.
* **Papel dos Desenvolvedores-Ponte e do `shadPS4`:** Cerca de $16,2\%$ dos desenvolvedores atuam em múltiplos projetos. A análise de *Betweenness* vs. *Eigenvector* e a decomposição em *k-shells* / *Onion Layers* demonstram que o `shadPS4` funciona como o principal repositório-ponte da Sony, atraindo especialistas veteranos do núcleo denso da Nintendo.

## Limitações e próximos passos
* **Limitações:** Janela de paginação da API limitada aos registros mais recentes (até $10$ páginas por *endpoint*) e ausência de distinção sobre quais módulos de código cada desenvolvedor alterou.
* **Próximos Passos:**
  1. Incorporar *timestamps* para modelar redes temporais de migração de desenvolvedores entre emuladores.
  2. Construir uma rede tripartida (*Dev $\leftrightarrow$ Subsistema Técnico $\leftrightarrow$ Emulador*) mapeando pastas específicas (ex.: `vulkan/`, `jit/`, `audio/`).
  3. Modelar redes dirigidas de revisão de código (*Pull Request reviews*) e expandir a coleta para emuladores de outras plataformas (`RPCS3`, `PCSX2`, `xenia`).

## Referências
* ROZEMBERCZKI, B.; ALLEN, C.; SARKAR, R. **Multi-scale Attributed Node Embedding** (*SNAP GitHub Social Network Dataset - musae-github*). Journal of Complex Networks, 2021.
* LATAPY, M.; MAGNIEN, C.; DEL VECCHIO, N. **Basic notions for the analysis of large two-mode networks**. Social Networks, v. 30, n. 1, p. 31-48, 2008.
* NEWMAN, M. **Networks**. 2nd ed. Oxford University Press, 2018.
* Documentação oficial do **NetworkX** (v3.x) e da **GitHub REST API** (v2022-11-28).
