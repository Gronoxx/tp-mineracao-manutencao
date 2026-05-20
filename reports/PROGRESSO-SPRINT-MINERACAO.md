# Progresso do Sprint de Mineração

**Período**: 2026-05-20 a 2026-06-10 (21 dias).
**Plano completo**: `reports/PLANO-SPRINT-MINERACAO.md` (ler em conjunto com este).

---

## ⚡ Como usar este documento (LEIA PRIMEIRO)

### Início de cada sessão nova

1. **Ler esta seção** (⚡ Como usar) e a seção **🎯 Estado Atual** abaixo.
2. **Ler a entrada mais recente em `📓 Log de Sessões`** (no fim do arquivo) para entender o que foi feito na última sessão e qual era o próximo passo.
3. **Conferir `🔀 Decisões Pendentes`** se houver itens bloqueando.
4. **Recorrer ao `PLANO-SPRINT-MINERACAO.md`** para detalhes de execução do dia atual (`§4. Execução`).
5. **Confirmar com o Gustavo** o plano da sessão antes de começar (a menos que o próximo passo seja inequívoco).

### Durante a sessão

- Foco no próximo passo concreto descrito em "Próxima ação".
- Atualizar **🎯 Estado Atual** quando algo muda (yield, branch, decisão).
- Anotar decisões novas em **🗂️ Decisões durante o sprint** (append-only).

### Fim de cada sessão (obrigatório)

1. **Atualizar `🎯 Estado Atual`** — dia, fase, yield, próxima ação.
2. **Adicionar nova entrada em `📓 Log de Sessões`** — data, atividades, resultado, bloqueadores, próxima ação.
3. **Snapshot de yield** se rodou mass mine ou análise — em `📊 Snapshots de yield`.
4. **Commit do PROGRESSO** (preferencialmente junto com qualquer outro PR da sessão; pode ser commit separado direto na main para PROGRESSO se não estiver mexendo em código).

---

## 🎯 Estado Atual (live)

> **Atualizar a cada sessão.**

### Onde estamos

- **Data da última atualização**: 2026-05-20
- **Dia do sprint**: 0 (planejamento; Dia 1 começa na próxima sessão)
- **Semana**: Pré-execução
- **Fase**: Plano declarado, aguardando início da execução

### Yield atual por smell

(Da mineração de produção do dia 19, ANTES das ações do sprint começarem)

| Smell | Estritos | Parciais | Total | Min viável | % do min | Status |
|---|---:|---:|---:|---:|---:|---|
| R1 Extract Method | 17 | 24 | 41 | 800 | 5% | ✗ |
| R2 Parameter Object | 26 | 27 | 53 | 600 (140 c/ r=8 attn) | 9% (38%) | ✗ |
| R3 Named Constant | 73 | 56 | 129 | 200 | 64% | borderline |
| R4 Guard Clauses | 95 | 32 | 127 | 400 | 32% | ✗ |
| R5 Remove Dead Code | 47 | 3 | 50 | 300 | 17% | ✗ |
| **Total** | **258** | **142** | **400** | | | |

### Próxima ação concreta

**Dia 1 do sprint** — atualizar schema com campo `source` + criar `data/test/`:

1. Branch `feature/source-tagging`.
2. Em `core/schema.py`, adicionar campo `source: Optional[Literal["mined_commit","mined_pr","adjacent_oracle","translated_java"]] = "mined_commit"`.
3. Criar `data/test/` (adicionar exceção em `.gitignore` se a regra `data/` cobrir).
4. Script de backfill: ler todos os `data/raw/*.jsonl`, adicionar `"source": "mined_commit"` aos registros existentes, regravar.
5. Testes em `tests/test_schema.py`.
6. Commit, push, PR, merge.

(Detalhes completos em `PLANO-SPRINT-MINERACAO.md §4 Semana 1 Dia 1`.)

### Branch / PR ativo

(nenhum no momento)

### Pendências / bloqueadores

- Email aos autores do ActRef pedindo replication package (não bloqueador, mas começar paralelo no Dia 2).

---

## 🔀 Decisões Pendentes (precisam decisão antes de avançar)

(Lista vazia no momento. Lista é populada quando aparece bloqueio que exige decisão Gustavo.)

| ID | Descrição | Quando | Status |
|---|---|---|---|
| (vazio) | | | |

---

## 🗂️ Decisões durante o sprint (append-only)

Decisões tomadas DURANTE a execução do sprint (≠ decisões do plano, que estão no `PLANO-SPRINT-MINERACAO.md §3`).

| Data | Decisão | Razão | Impacto |
|---|---|---|---|
| (vazio) | | | |

---

## 📊 Snapshots de yield

Snapshots gerados em pontos-chave do sprint.

### Snapshot pré-sprint (2026-05-19, mine de produção PR #19)

| Smell | Estritos | Parciais | Total |
|---|---:|---:|---:|
| R1 | 17 | 24 | 41 |
| R2 | 26 | 27 | 53 |
| R3 | 73 | 56 | 129 |
| R4 | 95 | 32 | 127 |
| R5 | 47 | 3 | 50 |
| **Total** | **258** | **142** | **400** |

Fontes: 35 repos minerados com sucesso (hypothesis falhou no clone por falta de git-lfs).

### Snapshot Fim Semana 1 (Dia 7)

*(a preencher após snapshot)*

### Snapshot Fim Semana 2 (Dia 14 — checkpoint crítico R5)

*(a preencher após snapshot)*

### Snapshot Final (Dia 21)

*(a preencher após snapshot)*

---

## 📓 Log de Sessões

> **Template para nova entrada (copiar e colar):**
>
> ### Sessão N — YYYY-MM-DD
>
> **Duração estimada**: X horas.
> **Dia do sprint**: N de 21.
>
> **Atividade**:
> - (o que foi feito)
>
> **Resultado**:
> - (saída concreta — PRs mesclados, yield gerado, etc.)
>
> **Bloqueadores**:
> - (se houver)
>
> **Próxima ação**:
> - (passo concreto para a próxima sessão)
>
> **Notas**:
> - (qualquer coisa que vale registrar — surprise, ajuste de threshold, observação)

---

### Sessão 1 — 2026-05-20 (PLANEJAMENTO)

**Duração estimada**: 3-4 horas (sessão longa de planejamento).
**Dia do sprint**: 0 (pré-execução).

**Atividade**:
- Análise dos resultados do mine de produção do dia anterior (PR #19, 400 pares produzidos).
- Discussão estratégica das 5 estratégias possíveis para expandir o dataset.
- Lançamento de 2 agentes de pesquisa: (a) LoRA data sizing (Opus, completo), (b) brainstorm de fontes de dado real (Opus, completo).
- Síntese dos relatórios em decisões concretas.
- Iteração sobre os 5 caminhos (perguntas detalhadas sobre cada um).
- Refinamento do plano em 3 iterações com Gustavo.
- Identificação dos 2 gaps no plano inicial: sourcing limpo (D5) e contradição R2.
- Decisão de adapter shrinking SÓ para R2 (D2). R5 wait-and-see (D3).
- Plano final declarado: 3 semanas, 5 smells mantidos, sem LLM hybrid, source tagging desde dia 1.
- Criação deste documento (PROGRESSO) e do `PLANO-SPRINT-MINERACAO.md`.

**Resultado**:
- 2 documentos criados em `reports/`:
  - `PLANO-SPRINT-MINERACAO.md` — plano completo com contexto, decisões, execução detalhada por dia, riscos, critérios de pronto, referências.
  - `PROGRESSO-SPRINT-MINERACAO.md` (este) — tracker live + log de sessões + snapshots.

**Bloqueadores**:
- Nenhum.

**Próxima ação**:
- **Dia 1 do sprint** começa amanhã (ou na próxima sessão). Detalhe completo em `PLANO-SPRINT-MINERACAO.md §4 Semana 1 Dia 1`. Resumo: branch `feature/source-tagging`, adiciona campo `source` no schema, cria `data/test/`, backfill dos 400 pares existentes, testes, PR, merge.
- Em paralelo no Dia 2: enviar email aos autores do ActRef pedindo replication package.

**Notas**:
- O plano assume implementação ágil com IA assistindo. Custo realista do Caminho 5 (rename-aware) estimado em 5-8 dias focados, não 15+.
- Gates de validação (precision em amostra cross-file, behavioral check) são críticos pra confiar no Caminho 5 — não pular.
- Checkpoint do dia 14 é o ponto onde a estratégia R5 vai ser concretizada. Não improvisar antes desse checkpoint.
- Caminho 1 (LLM hybrid) está descartado **provisoriamente** — pode voltar se Caminho A (adapter shrink) falhar no smoke training do Dia 17.

---

## 🧭 Mapa rápido — onde estão as coisas

| Coisa | Onde |
|---|---|
| Plano completo | `reports/PLANO-SPRINT-MINERACAO.md` |
| Estado atual | aqui (este arquivo, §🎯) |
| Próxima ação | aqui (este arquivo, §🎯 → "Próxima ação concreta") |
| Decisões do plano | `reports/PLANO-SPRINT-MINERACAO.md §3` |
| Decisões durante sprint | aqui (§🗂️) |
| Resultado mine pré-sprint | `reports/2026-05-20-mine-resultado.md` |
| Engine de mineração | `extracao/mineracao/minerador.py` |
| Runner de produção | `extracao/execucao/mineracao.py` |
| Schema | `core/schema.py` |
| Curador (revisão dupla) | `extracao/execucao/filtro_smells.py` |
| Treino LoRA | `trilha_b/training/` |
| Testes | `tests/` |
| Logs de execuções anteriores | `logs/` |
