# Demonstração da CLI — material para o relatório

Saídas reais da ferramenta (`cli.py`), capturadas em 2026-06-15, prontas para
citar/screenshotar no relatório do TP. Para reproduzir, rode os comandos abaixo
da raiz de `tp-mineracao-manutencao`.

## Instalação

```bash
pip install -r detectores/requirements.txt click rich
```

## 1. Listar os smells suportados

```bash
python3 cli.py smells
```

```
                               Smells suportados
┏━━━━┳━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ ID ┃ Smell           ┃ Descrição                                             ┃
┡━━━━╇━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ R1 │ long_method     │ Método longo / complexo demais — candidato a Extract  │
│    │                 │ Method                                                │
│ R2 │ long_param_list │ Lista de parâmetros longa — candidato a Parameter     │
│    │                 │ Object                                                │
│ R3 │ magic_numbers   │ Números mágicos — candidato a Named Constant          │
│ R4 │ deep_nesting    │ Aninhamento profundo — candidato a Guard Clauses      │
│ R5 │ dead_code       │ Código morto — candidato a remoção                    │
└────┴─────────────────┴───────────────────────────────────────────────────────┘
```

## 2. Analisar um arquivo (saída em árvore)

```bash
python3 cli.py scan gemma_judge_dataset.py
```

```
gemma_judge_dataset.py
├── call_gemma (linha 151)
│   ├── R1 long_method — 35 linhas (limite 30), complexidade 12 (limite 10)
│   └── R3 magic_numbers — 1 literais mágicos: 3
└── main (linha 201)
    ├── R1 long_method — 95 linhas (limite 30), complexidade 23 (limite 10)
    ├── R3 magic_numbers — 10 literais mágicos: 5, 5, 20, 60, 60 (+5)
    └── R4 deep_nesting — profundidade máxima 4 (limite 3)
              Resumo
┏━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━┓
┃ Smell              ┃ Detecções ┃
┡━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━┩
│ R1 long_method     │         2 │
│ R2 long_param_list │         0 │
│ R3 magic_numbers   │         2 │
│ R4 deep_nesting    │         1 │
│ R5 dead_code       │         0 │
└────────────────────┴───────────┘
```

A árvore reflete a estrutura do código: arquivo → função/método (com linha) →
smells detectados, cada um com a **evidência métrica** que disparou a detecção
(linhas, complexidade ciclomática, contagem de parâmetros, profundidade de
aninhamento, literais).

## 3. Outras formas de uso

```bash
python3 cli.py scan extracao/                       # diretório recursivo
python3 cli.py scan src/ --smell long_method --smell dead_code   # filtrar smells
python3 cli.py scan src/ --json > resultado.json    # saída para agregação/métricas
python3 cli.py scan src/ --fail-on-detect           # exit code 1 se achar algo (CI)
```

O modo `--json` emite, por função, o smell e o dicionário de evidência — base
para qualquer agregação ou visualização no relatório. Exemplo de registro:

```json
{"funcao": "is_valid_pair", "lineno": 66,
 "smells": [{"smell": "magic_numbers",
             "evidence": {"magic_numbers": [{"value": 10, "lineno": 10}]}}]}
```

## 4. Estudo de caso: a ferramenta sobre o próprio código (dogfooding)

Rodando a CLI sobre o próprio repositório de código do projeto
(`detectores/ extracao/ core/`, 23 arquivos):

```bash
python3 cli.py scan detectores/ extracao/ core/ --json
```

| Métrica | Valor |
|---|---|
| Arquivos analisados | 23 |
| Funções/métodos com ≥1 smell | 24 |
| R1 long_method | 13 |
| R2 long_param_list | 5 |
| R3 magic_numbers | 11 |
| R4 deep_nesting | 11 |
| R5 dead_code | 0 |

Exemplo concreto encontrado — a própria função de mineração tem lista de
parâmetros longa (R2) e aninhamento profundo (R4):

```
└── mine_specific_commits (linha 477)
    ├── R1 long_method — 40 linhas (limite 30), complexidade 15 (limite 10)
    ├── R2 long_param_list — 7 parâmetros (limite 5): repo_url, output_path,
    │   commit_hashes, partial_threshold, source, clone_repo_to, only_no_merge
    └── R4 deep_nesting — profundidade máxima 4 (limite 3)
```

Serve de validação de sanidade (a ferramenta encontra smells reais em código de
produção) e de gancho honesto para o relatório: a detecção é o primeiro passo;
a *refatoração* desses casos é a Trilha B (em desenvolvimento).

## 5. Cobertura vs. enunciado

| Requisito do enunciado | Onde a CLI atende |
|---|---|
| Ferramenta CLI de identificação de problemas de manutenção | `cli.py scan` |
| Mineração de repositórios | modo diretório/repo + pipeline `extracao/` |
| Artefatos analisados (código) | decomposição AST em funções/métodos |
| Apresentação de resultados (métricas/visualização) | árvore Rich + tabela-resumo + `--json` |

> Limiares de detecção (R1 NLOC>30 ou CCN>10; R2 >5 params; R4 profundidade >3;
> R3 whitelist {0,1,2}) são convenções de literatura (McCabe, Pylint R0913/R1702),
> deliberadamente estritas. Calibração por percentil sobre o corpus é trabalho
> futuro (Trilha 2) — ver `docs/DECISOES_PROJETO.md`.
