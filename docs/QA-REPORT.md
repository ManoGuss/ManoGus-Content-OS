# QA & System Audit — MANOGUS CONTENT OS

Data: 2026-09-29. Escopo: cópia local da implementação Foundation → Script Engine em `/workspace/scratch/7f4560866703`. Este diretório não contém `.git`; não foi possível confirmar se é a versão canônica nem auditar histórico de commits. Uma implementação anterior e distinta de Revenue OS existe em outro diretório, mas não integra esta cópia. Os documentos de arquitetura mestre não estão nesta árvore; a comparação documental se limita a `README.md` e `docs/IMPLEMENTATION-STATUS.md`.

## Verificação

- `python -m pytest tests -q`: **5 passed**, três avisos de depreciação.
- `cd frontend && npm run build`: **passou** (TypeScript e Vite).
- Inspeção estática de endpoints, migrations SQLite, componentes React, serviços de pesquisa, Trends, referências, roteiro, testes e histórico declarado em `IMPLEMENTATION-STATUS.md`.
- Sem chave YouTube, modelo Ollama ou navegador de teste nesta execução: integrações ao vivo e cliques não foram testados de ponta a ponta. Achados de interface abaixo são demonstrados pelo fluxo do código, salvo indicação contrária.

## CRITICAL

**C1 — API mutável sem autenticação ou proteção de origem.** Local: `backend/app/main.py:40-46,81-184`, routers em `research.py`, `trends.py`, `reference_analyzer.py`, `script_engine.py`; `frontend/vite.config.ts`. Causa: fase local ainda sem login/CSRF e sem verificação de `Origin`/`Host` nas mutações. Impacto: qualquer cliente capaz de alcançar a porta pode criar/alterar conteúdo, ler transcripts e gerar backups; um navegador local também pode ser induzido a enviar requisições, dependendo do contexto de origem. Correção: autenticação local, verificação de origem/host e CSRF para mutações, limites de acesso e teste de rejeição; manter bind exclusivamente em loopback até isso existir. **Não há evidência de exploração nesta auditoria.**

## HIGH

**H1 — Backup não contém seu próprio registro e pode deixar arquivo órfão.** Local: `backend/app/main.py:171-181`. Causa: `c.backup(dest)` ocorre antes do `INSERT INTO backups`; falha posterior deixa arquivo sem registro. Impacto: após restauração, o catálogo e a trilha de auditoria não refletem a cópia criada; acumulação de arquivos órfãos. Correção: especificar semântica de backup, registrar e confirmar metadados antes da cópia ou acompanhar manifest externo, limpar arquivos em erro e testar restauração/consistência.

**H2 — Estado de projeto/roteiro pode vazar entre seleções na interface.** Local: `frontend/src/main.tsx:12,25`; `frontend/src/ScriptEditor.tsx:5-8`. Causa: `ScriptEditor` não tem `key` por projeto e `reload()` assíncrono não cancela respostas antigas ao trocar de projeto. Impacto: conteúdo do projeto A pode aparecer durante a abertura do B e ser enviado ao endpoint de B; risco de versão indevida. Correção: chavear componente por `project.id`, invalidar respostas pendentes, desabilitar edição até carregar o roteiro correto e testar troca rápida A→B.

**H3 — Contexto de três referências pode ignorar análises existentes.** Local: `backend/app/script_engine.py:124-132`. Causa: `LIMIT 3` é aplicado às referências antes de filtrar as que têm análise. Impacto: três referências sem análise no início da lista bloqueiam referências analisadas seguintes na geração Ollama. Correção: selecionar as três análises mais recentes/elegíveis com JOIN, preservando ordem e proveniência; testar quatro referências com apenas a quarta analisada.

**H4 — Separação dos canais no Radar é visualmente inconsistente.** Local: `frontend/src/Radar.tsx:7-8`; `backend/app/research.py:169-180` e schema `002_research.sql`. Causa: histórico de buscas global, sem vínculo de canal em `source_runs`; ao abrir Radar de qualquer canal, carrega o último run global. Impacto: resultados pesquisados sob MANOGUS aparecem em MANOGUSSS, apesar do seletor e da pontuação de oportunidade por canal. Correção: associar run ao canal ou rotular claramente pesquisa como global e filtrar somente oportunidades por canal; migrar schema e testar alternância.

## MEDIUM

**M1 — Capabilities e textos da interface estão obsoletos.** Local: `backend/app/main.py:162-167`, `frontend/src/main.tsx:26`, `README.md`. Causa: `/capabilities` declara research `UNAVAILABLE` e Analytics `BLOCKED_EXTERNAL_CONFIG`; interface diz geração IA `COMING SOON` e README diz que não está exposta, embora Radar e geração Ollama existam. Impacto: configuração enganosa e diagnóstico incorreto. Correção: calcular estados reais por módulo e atualizar textos/README; Analytics deve refletir ausência de implementação nesta cópia.

**M2 — Nota fixa 3/5 recebe aparência de avaliação específica.** Local: `frontend/src/Radar.tsx:10-11`; `backend/app/research.py:199-211`. Causa: UI envia oito notas constantes e apenas pede uma justificativa; o backend calcula 60/100 para todo vídeo. Impacto: Click Appeal persistido e exibido como inferência editorial individual apesar de a rubrica não ter sido preenchida. Correção: expor os oito critérios editáveis e exigir evidência correspondente, ou rotular explicitamente como placeholder e impedir seu uso no Opportunity Score.

**M3 — Corrida na carga das listas ao trocar de canal.** Local: `frontend/src/main.tsx:9-10`. Causa: `refresh` não cancela nem verifica a identidade do canal antes de aplicar respostas. Impacto: resposta atrasada do canal anterior pode preencher ideias, projetos e dashboard sob o canal novo. Correção: `AbortController` ou token de geração por requisição; teste com respostas fora de ordem.

**M4 — Configurações persistidas sem efeito observável.** Local: `backend/app/main.py:148-161`, `frontend/src/ScriptEditor.tsx:5`, `frontend/src/ReferenceAnalyzer.tsx`. Causa: `ollama_model` e `timezone` podem ser gravados na API, mas editor usa `llama3.2` fixo e nenhuma conversão lê `timezone`. Impacto: dados persistidos sugerem preferência aplicada, mas a operação a ignora. Correção: vincular modelo aos componentes e timezone à apresentação, ou remover ajustes inativos da API.

**M5 — Histórico de migração não é rastreado.** Local: `backend/app/main.py:32-46`, migrations `001` a `005`. Causa: scripts `CREATE TABLE IF NOT EXISTS` são reexecutados no startup sem tabela de versões e checagem de compatibilidade. Impacto: mudanças futuras de colunas/constraints não seriam aplicadas a bancos existentes, com erro tardio em runtime. Correção: migration runner versionado e teste de upgrade de banco anterior.

## LOW

**L1 — Mensagem de erro perde rascunho.** Local: `frontend/src/ScriptEditor.tsx:8,12`. Causa: botão `Recarregar` após falha substitui conteúdo local sem aviso. Impacto: perda de edição não salva. Correção: avisar e permitir copiar/recuperar rascunho antes de recarregar.

**L2 — Histórico e logs parciais.** Local: `backend/app/main.py:56,168-184`, `docs/IMPLEMENTATION-STATUS.md`. Causa: auditoria cobre apenas certas mutações e não há restauração de backup/projeto pela UI. Impacto: rastreabilidade e recuperação limitadas; documentação já classifica essas capacidades como parciais. Correção: definir cobertura de eventos, verificação de integridade e fluxo de restauração antes de promover a disponibilidade.

**L3 — Avisos de depreciação.** Local: `backend/app/main.py:40`; ambiente de teste Starlette/httpx. Causa: `on_event` obsoleto e dependência de TestClient legada. Impacto: manutenção futura. Correção: migrar startup para lifespan e fixar/atualizar dependências de teste compatíveis.

## Prioridade e resultado

Corrigir primeiro C1 e H2 antes de qualquer uso fora do próprio computador; em seguida H1, H3 e H4. Não foram feitas alterações no código nesta auditoria: as correções de segurança, migração e sincronização de estado exigem testes específicos e a cópia auditada não possui vínculo confirmado com o repositório canônico. Os testes existentes passam, mas não cobrem os cenários H1–H4 e M2–M3. Depois de cada correção, repetir os testes Python, build frontend e testes de regressão correspondentes.
