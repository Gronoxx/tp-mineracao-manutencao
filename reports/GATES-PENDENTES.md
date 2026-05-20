# Gates Pendentes — Sprint de Mineração

> **Leia este documento ANTES de continuar o sprint.** Lista gates de
> qualidade que precisam ser executados (alguns BLOQUEIAM avanço para
> próximos dias, outros são paralelos).
>
> Status referente ao fim da Sessão 10 (2026-05-20, fim do overnight).
> Plano-mãe: `reports/PLANO-SPRINT-MINERACAO.md`.

---

## ⚡ Resumo executivo

| Gate | Bloqueia | Quando rodar | Custo estimado | Status |
|---|---|---|---:|---|
| Inspeção automática dos pares adjacent_oracle (G0) | Dia 11 | Pronto pra rodar | 1s | ✓ EXECUTADO |
| Calibração de threshold AST cross-file (G1) | Mass mine #2 com cross-file | Depende de G2 | 30min | PENDENTE |
| Calibração de threshold identifier overlap (G1') | Mass mine #2 com cross-file | Depende de G2 | junto com G1 | PENDENTE |
| Behavioral check em amostra de pares cross-file (G2) | G1, G1' | Depende de mass mine #2 produzir cross-file pairs | 30-60min | PENDENTE |
| Smoke yield-delta `require_keyword=False` (G3) | Decisão de usar `require_keyword=False` no mass mine | Antes do mass mine #2 | 30-60min (3 repos) | PENDENTE |
| Quality check automático em CADA mass mine (G4) | É um gate de regressão | Pós-mass mine | 1s | PRONTO PRA RODAR |
| Inspeção manual de WARN agregados por commit (G5) | Não bloqueia, mas reduz incerteza | Após qualquer mass mine | 5-30min/mass mine | PENDENTE |

---

## G0 — Inspeção automática dos pares adjacent_oracle ✓ EXECUTADO

**O que é:** rodar `scripts/quality_check_pairs.py` nos 25 pares produzidos pelo
`mine_specific_commits` no Dia 3 (catálogo PyRef).

**Por que importa:** o `mine_specific_commits` bypassa o filtro de keyword e
usa `partial_threshold=0.1` (modo permissivo). Antes de declarar adjacent
mining seguro, precisamos verificar que os pares produzidos não são FP
estruturais.

**Resultado (Sessão 10):**

```
=== Quality Check — 25 pares ===
  CLEAN: 22  (88.0%)
  WARN:  3  (12.0%)
  FAIL:  0  (0.0%)
```

Os 3 WARNs vieram TODOS da mesma função (`dit/helpers.py::reorder`),
emitidos em 3 smells diferentes (R2, R3, R4) — característica de
refatoração drástica que dispara múltiplos smells. AST similarity ≈ 0.27
(borderline, não fail). Não é FP confirmado, mas vale uma olhada visual
quando houver tempo.

**Critério de pass aplicado:** 0 FAILs e <20% WARNs. ✓ ATINGIDO (12% WARN).

**Conclusão:** `mine_specific_commits` aprovado para uso em produção sem
restrições. Os 25 pares `adjacent_oracle` em `data/raw/` estão limpos
automaticamente.

---

## G1 — Calibração de threshold AST cross-file 🚧 PENDENTE (alta prioridade)

**O que é:** rodar o pipeline cross-file (`mine(cross_file_threshold=X)`) em
amostra com X variando em {0.5, 0.6, 0.7, 0.8, 0.9}, medir precision em cada
threshold via behavioral check (G2) ou inspeção manual de amostra.

**Por que importa:** o threshold default no `mine()` é `None` (desligado).
Quando ligado, o valor sugerido pelo plano é 0.7, mas é PALPITE — não
empírico. Pegar um valor errado pode:
- Threshold muito baixo: aceitar FPs (funções estruturalmente similares mas
  semanticamente diferentes — duas `validate_input` em domínios distintos).
- Threshold muito alto: descartar TPs (refatorações genuínas que mudam
  bastante estrutura).

**Dependência:** precisa de G2 (behavioral check) como signal de ground
truth, OU inspeção manual de ~50 pares.

**Como rodar:**

> ⚠️ **NOTA**: `extracao/execucao/mineracao.py` é o runner de produção mas
> NÃO tem CLI parser (REPOS hardcoded). Para rodar `mine()` com
> `cross_file_threshold`, use a API Python direta OU estenda o runner
> com argparse (PR pequeno, ~15 linhas).

```python
# 1. Produzir pares cross-file num mass mine separado (e.g., 3 repos pequenos)
from extracao.mineracao.minerador import mine
from pathlib import Path
for repo in ["flask", "click", "requests"]:
    mine(repo_url=f"https://github.com/pallets/{repo}",
         output_path=Path("data/raw_calibration"),
         cross_file_threshold=0.5)  # threshold permissivo p/ ter universo

# 2. Filtrar os pares com source="cross_file" (D5 do sprint)
python3 scripts/quality_check_pairs.py \
    --raw-dir data/raw_calibration --source cross_file --verbose

# 3. Para cada threshold candidato, filtrar + rodar behavioral check
#    (Script calibrate_cross_file.py ainda NÃO existe — criar quando rodar.)
```

**Critério de pass do plano:** escolher o menor threshold com precision > 0.7
(plano §4 Dia 6-7 item 6).

**Decisão sobre quando ativar cross-file:** **NÃO ativar em produção até
G1 + G2 passarem**. O `cross_file_threshold` no mass mine #2 deve ficar
inicialmente em `None` (desligado). Após G1 passar, ativar com o threshold
calibrado num mass mine #3.

---

### Pré-requisito do G1 (já resolvido na Sessão 11)

Pares cross-file recebem `source="cross_file"` (Literal estendido no schema).
Antes desta correção, pares cross-file ficavam indistinguíveis dos per-file
(`source="mined_commit"` em ambos) — não havia como filtrá-los para
calibração. Schema corrigido + propagação em `mine()` ajustada.

---

## G1' — Calibração de threshold identifier overlap 🚧 PENDENTE

**O que é:** mesmo formato de G1, mas para o `identifier_overlap_threshold`
(Jaccard sobre identificadores).

**Por que importa:** complementa G1. AST similarity captura forma, identifier
overlap captura vocabulário. O threshold sugerido (0.5) é PALPITE.

**Como rodar:** junto com G1, variando o segundo eixo.

**Decisão:** sem calibração, manter em 0.0 (filtro desligado). Não ligar
ambos os filtros sem calibração — risco de filtro duplo derrubar TPs.

---

## G2 — Behavioral check em amostra de pares cross-file 🚧 PENDENTE

**O que é:** rodar `extracao/mineracao/behavioral_check.py` em uma amostra de
50 pares cross-file (depois de mass mine #2 produzir pares com
`source="cross_file"`).

**Por que importa:** behavioral check é a única validação de PRECISION que
não depende de inspeção humana. Funciona executando ambas as funções com
inputs aleatórios (via `hypothesis`) e comparando outputs.

**Caveat conhecido:** o behavioral check tem altas taxas de "inconclusive"
para funções que dependem de imports/contexto externo (a maioria das
funções de repos reais). Funções puras simples são as únicas em que dá
sinal claro. Por isso o uso é AMOSTRADO + interpretado como "taxa de
equivalência entre os pares COMPARÁVEIS".

**Critério de pass do plano:** taxa de aprovação > 70% → pipeline cross-file
confiável. < 50% → ajustar thresholds (volta para G1).

**Como rodar:**

```python
# 1. Rodar mass mine separado (não o #2) com cross-file ativado
#    em 3-5 repos pequenos
from extracao.mineracao.minerador import mine
from pathlib import Path
for repo in ["flask", "click", "requests"]:
    mine(repo_url=f"https://github.com/pallets/{repo}",
         output_path=Path("data/raw_calibration"),
         cross_file_threshold=0.5)

# 2. Carregar pares com source="cross_file" e amostrar 50
# 3. Rodar behavioral_check em cada um
from extracao.mineracao.behavioral_check import behavioral_check
# ... (script calibrate_cross_file.py a criar)
```

**Dependência:** rodada separada de mineração só pra calibração — NÃO o
mass mine #2 de produção (que mantém cross-file DESLIGADO conforme G1).

---

## G3 — Smoke yield-delta `require_keyword=False` 🚧 PENDENTE

**O que é:** comparar yield em 3 repos pequenos (flask, click, requests) com
`require_keyword=True` (default) vs `False`, para entender o ganho
proporcional e a possível introdução de ruído.

**Por que importa:** o plano §4 Dia 4 explicitamente pediu esse smoke. Sem
isso, não sabemos se ativar `require_keyword=False` no mass mine #2 vai
multiplicar o yield 10x (bom) ou 100x com 90% FP (ruim).

**Como rodar:**

```bash
for repo in flask click requests; do
    for kw in True False; do
        python3 -c "
from extracao.mineracao.minerador import mine
from pathlib import Path
counts = mine(
    repo_url=f'https://github.com/pallets/{repo}',
    output_path=Path('/tmp/smoke_${repo}_${kw}'),
    require_keyword=$kw,
)
print(f'{repo} kw={kw}: {counts}')
"
    done
done
```

**Critério de pass:** yield com `require_keyword=False` deve ser <10x o
yield com `True` para que o quality check (G4) seja tratável. Se for >100x,
provavelmente carrega muito FP — manter `require_keyword=True` no mass mine #2.

---

## G4 — Quality check automático em CADA mass mine ✓ PRONTO PRA RODAR

**O que é:** rodar `scripts/quality_check_pairs.py` no resultado de toda
mass mineração, como gate de regressão.

**Por que importa:** sem isso, qualquer mudança no minerador que introduza
FP estrutural passa silenciosamente. O quality check é estático (rápido,
sem rede, sem executar código) — custo desprezível.

**Como rodar:**

```bash
# Após mass mine #2
python3 scripts/quality_check_pairs.py --raw-dir data/raw

# Filtrado por source (pra ver o impacto de cada caminho)
python3 scripts/quality_check_pairs.py --source mined_pr --verbose
python3 scripts/quality_check_pairs.py --source cross_file --verbose
```

**Critério de pass:** 0 FAILs. WARN <20%.

**Decisão de processo:** integrar ao runner do mass mine como gate
automático — exit code != 0 do quality check deve abortar análise
posterior (Dia 13).

---

## G5 — Inspeção manual de WARN agregados por commit 🚧 PENDENTE (opcional)

**O que é:** quando o quality check (G4) reporta WARNs, agregar por commit
(igual ao caso do `dit/helpers.py::reorder` em G0) e pedir uma inspeção
visual dos commits "suspeitos".

**Por que importa:** WARNs não são FPs, mas concentração de WARNs no mesmo
commit pode indicar refatoração drástica genuína OU um bug de pareamento
específico daquela situação.

**Critério:** se >3 WARNs vêm do mesmo commit, vale 5 min de olhar pra
decidir.

**Status:** opcional. Dia 11 pode pular se quality check (G4) ficar < 5%
WARN.

---

## Resumo de decisões para Dia 11

A partir desta documentação, as **decisões padrão para o Dia 11** são:

1. ✅ **`require_keyword=False`** → NÃO ativar sem G3 rodado primeiro.
   Manter mass mine #2 com `require_keyword=True` (default) inicialmente.

2. ✅ **`cross_file_threshold`** → NÃO ativar no mass mine #2 (manter
   `None`). Cross-file requer G1+G2 calibrados.

3. ✅ **`identifier_overlap_threshold`** → idem, manter 0.0.

4. ✅ **`mine_pr` via `data/pr_list.json`** → SEGURO PARA ATIVAR.
   `mine_pr` reutiliza o detector estrito + estrutura conservadora, sem
   FP novo previsto. Sugestão: rodar G4 (quality check) imediatamente
   após para confirmar.

5. ✅ **`mine_specific_commits` adjacent_oracle** → JÁ APROVADO (G0
   passou com 0 FAILs).

**Em resumo: o mass mine #2 pode rodar em modo COMBINADO conservador
(commit + PR + adjacent), com cross-file DESLIGADO. Cross-file precisa de
calibração separada antes de entrar em produção.**

---

## Como atualizar este documento

- Quando um gate for executado e passar: marcar ✓ EXECUTADO com data e
  resumo do resultado.
- Quando um gate falhar: marcar ❌ FALHOU + ação corretiva tomada.
- Quando surgir gate novo (ex.: novo caminho de mineração): adicionar
  como Gn+1 com mesmo formato.
- Manter a tabela de resumo no topo sincronizada.
