# MANOGUS CONTENT OS — estado da implementação

2026-09-29 · Foundation vertical slice 0.1

| Módulo | Estado | Evidência |
| --- | --- | --- |
| Channel Manager | IMPLEMENTADO (seleção e isolamento) | `channels`, `channel_id` nos endpoints |
| Dashboard | IMPLEMENTADO (contagens locais) | `/api/v1/dashboard` |
| Idea Vault | IMPLEMENTADO (criação e promoção) | `/api/v1/ideas` |
| Project Manager | IMPLEMENTADO (editar/salvar/reabrir) | `/api/v1/projects` e revisão otimista |
| Reference Library | PARCIAL | Referências manuais por projeto; catálogo/análise posterior |
| Checklist | IMPLEMENTADO | Persistência e conclusão de tarefas |
| Settings | PARCIAL | Capabilities e backup; editor de configurações posterior |
| AIProvider/OllamaProvider | PARCIAL | Abstração e detecção; geração via UI futura |
| Logs/auditoria | PARCIAL | Audit trail persistido; JSON/rotação futura |
| Backup | PARCIAL | SQLite online backup; verificação/restore futuro |
| Versioning | PARCIAL | Snapshot anterior a cada edição do projeto; restauração futura |
| Login local, OAuth, Analytics, Research, Revenue | NÃO DISPONÍVEL / BLOQUEADO | Não expor API fora de localhost; autenticação owner é próxima fatia crítica |

Teste funcional: criar ideia → promover → adicionar referência e tarefa → editar projeto → recarregar/reabrir; ver `tests/test_flow.py`. Dados dos canais são apenas nomes e focos, sem métricas fictícias. IDs oficiais do YouTube aguardam confirmação. Não expor o servidor à rede até autenticação local e CSRF.

## Fase 2 — YouTube Research vertical slice (2026-09-29)

| Capacidade | Estado | Evidência e limite |
| --- | --- | --- |
| YouTube Data API, keyword, filtros 7/90/180 | IMPLEMENTADO, BLOQUEADO POR CONFIGURAÇÃO EXTERNA para uso real | `YOUTUBE_API_KEY`; busca `search.list`, hidratação `videos.list`, primeira página até 50 resultados |
| Catálogo e snapshots | IMPLEMENTADO | Migration `002_research.sql`; snapshot apenas de resposta nova da API; refresh manual |
| Views/day e Average VPH | IMPLEMENTADO | Médias desde publicação, idade mínima 1h |
| Observed VPH e Recent VPH 1/6/12/24h | IMPLEMENTADO | Pares reais, tolerância de janela e correção de contador; `null` sem amostra |
| Outlier Score | IMPLEMENTADO CONDICIONAL | Cinco vídeos anteriores do mesmo criador/tipo/duração com observações em idade comparável; normalmente indisponível até haver histórico |
| Click Appeal Score | PARCIAL | Avaliação manual com oito notas e evidência registrada; UI usa rubrica fixa 3/5, editor completo de notas pendente; jamais CTR |
| Opportunity Score | PARCIAL | Cálculo condicional por canal com tendência longitudinal e outlier; sem amostra suficiente devolve `null` e razões; não há Trends nem Style DNA no score v1 |
| Quota ledger, cache, worker/scheduler, retry, paginação | NÃO IMPLEMENTADO | Buscar manualmente consome quota por chamada; não há coleta automática |
| Google Trends e Analytics privado | NÃO IMPLEMENTADO | Fora desta fatia |

Testes: `python -m pytest tests/test_flow.py tests/test_research.py -q`; fixture da API valida descoberta, deduplicação, persistência, segundo snapshot, métricas e ausência honesta de score. `npm run build` no frontend. Sem chave de API real nesta execução; integração externa ao vivo não verificada. A chave só é lida de variável de ambiente do backend. O app permanece restrito a localhost, sem login nesta fatia.

## Google Trends Adapter — importação manual (2026-09-29)

| Capacidade | Estado | Evidência |
| --- | --- | --- |
| `TrendsAdapter` / `ManualCsvTrendsAdapter` | IMPLEMENTADO | Parser CSV com cabeçalho temporal, uma série, intervalos e índices 0–100 |
| Importar, listar e reabrir séries | IMPLEMENTADO | Migration `003_trends.sql`, endpoints `/api/v1/trends/import` e `/api/v1/trends/series`, tela Trends |
| Proveniência e normalização | IMPLEMENTADO | Fonte HTTPS Google Trends declarada, região, janela, grupo, método e hash de deduplicação |
| Google Trends API alpha automática | BLOQUEADO POR ACESSO EXTERNO | Sem credencial/convite alpha; nenhum scraping ou coleta automática |
| Integração de Trends ao Opportunity Score | NÃO IMPLEMENTADO | Não misturar escalas de exportações independentes; exige normalização e contrato adicional |

Verificação: `python -m pytest tests/test_flow.py tests/test_research.py tests/test_trends.py -q` (3 passaram) e `npm run build`. O teste inclui importação, deduplicação, validação de índices/colunas e reabertura após reinício. O fluxo real de arquivo exportado pelo Google não foi exercido nesta sessão; a UI aceita o CSV oficial de uma série por vez.

## Reference Analyzer — primeira fatia (2026-09-29)

| Capacidade | Estado | Evidência |
| --- | --- | --- |
| Análise estrutural por referência/projeto | IMPLEMENTADO | Migration `004_reference_analyzer.sql`, API `/api/v1/references/{id}/analyze`, tela no Project Workspace |
| Título e miniatura | PARCIAL | Mecanismo e evidência manual; nenhuma imagem é baixada/analisada automaticamente |
| Transcript autorizado | IMPLEMENTADO (texto fornecido) | Origem, nota de direitos, idioma e hash; nenhuma busca de captions de terceiros |
| Anotações narrativas | PARCIAL | Schema de beats/evidência/tempo/confiança; UI permite uma anotação por versão, API aceita até 30 |
| Ollama | PARCIAL / BLOQUEADO POR CONFIGURAÇÃO EXTERNA | Geração local opcional e validação de JSON; rascunhos classificados como inferência, nunca substituem análise anterior |
| Versões e fonte alterada | IMPLEMENTADO | Versões append-only com hash de título/URL/notas/transcript; `stale` quando fonte difere |
| Processamento de mídia/faster-whisper | NÃO IMPLEMENTADO | Texto manual é o fallback real |

Verificação: 4 testes passaram (`tests/test_reference_analyzer.py` inclui ausência de transcript, autorização, versões, reabertura e Ollama indisponível); frontend compilou. Sem modelo Ollama instalado nesta sessão, geração real não foi verificada. O texto do transcript fica no banco local e no backup: configure o dispositivo para proteger os dados. Não há certificação de direitos ou originalidade.

## Script Engine — vertical slice (2026-09-29)

| Capacidade | Estado | Evidência |
| --- | --- | --- |
| Roteiro por projeto e canal | IMPLEMENTADO | Migration `005_script_engine.sql`, `scripts`, `script_versions`, API e editor no Project Workspace |
| Cenas editáveis e ordem narrativa | IMPLEMENTADO | IDs estáveis, objetivo, beat, duração, narração, gameplay, visual e notas; cada edição salva nova versão |
| Histórico, revisão concorrente e restauração | IMPLEMENTADO | Revisão otimista 409, snapshots imutáveis, restauração como nova revisão |
| Análise estrutural | PARCIAL | Alertas para hook, promessa, open loop/payoff e plano visual; heurística editorial, não retenção observada |
| Geração por Ollama | PARCIAL / BLOQUEADO POR CONFIGURAÇÃO EXTERNA | Usa ideia e até três análises de referências; JSON validado, 3–12 cenas, rascunho versionado; requer Ollama/modelo local |
| Style DNA, pesquisa e transcrição própria no contexto | NÃO IMPLEMENTADO | `UNAVAILABLE` registrado no contexto, sem inventar dados |
| Editor avançado, diff de cenas, aprovação editorial e Originality Checker | NÃO IMPLEMENTADO | Próximas fatias |

Verificação: `python -m pytest tests/test_flow.py tests/test_research.py tests/test_trends.py tests/test_reference_analyzer.py tests/test_script_engine.py -q` (5 passaram); `npm run build` (passou). Testes incluem criação, reabertura, isolamento de cena, conflito 409, restauração e Ollama simulado/falha. Modelo Ollama real não foi executado nesta sessão. Roteiros gerados são rascunhos para revisão humana.

## Project Workspace — fluxo diário mínimo (2026-09-29)

- **IMPLEMENTADO:** criação direta de projeto (com ideia associada), promoção de ideia, seleção de canal, Overview editável, até 3 referências principais por projeto, checklist com conclusão, roteiro/cenas versionados, reabertura persistida. Navegação do workspace: Overview, References, Script e History informativo.
- **PARCIAL:** History mostra onde consultar versões; auditoria existe na API, mas não há timeline integrada. Referências têm URL e análise, mas não seleção automática a partir do Radar. Task/checklist ainda não tem categoria, prazo ou prioridade.
- **COMING SOON:** abas Research, Production, Thumbnail, SEO, Shorts, Analytics, Revenue, Sponsors e telas correspondentes; não existem botões que afirmem executar esses fluxos.
- **BLOQUEADO POR CONFIGURAÇÃO EXTERNA:** YouTube Data API e Ollama reais; nenhuma métrica externa foi semeada.
- **Teste:** `tests/test_daily_flow.py` cobre 3 referências, roteiro/cenas, tarefa concluída, persistência após reabertura e isolamento dos canais; suíte completa 7 testes passou. Frontend compilou.

Segurança pendente: autenticação local/CSRF antes de acesso por rede. O servidor permanece vinculado a `127.0.0.1`. Não há execução de um navegador real no ambiente do usuário; os testes de API e build não substituem esse teste manual.
