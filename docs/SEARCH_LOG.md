# Search log (sequential, one-at-a-time per rate-limit discipline)

Date: 2026-10-02. Order executed strictly sequentially (no parallel websearch):

1. `websearch` (Exa-equivalent): "Patrick Nill Robbins World Cup trading strategy DAX oil 2026" -> IQ Capital story (PVD, counter-trend, 1%/2-3%, oil -$37 lesson), YouTube transcripts, standings (302.6%/202.1%/100.5%), patrick-nill.com.
2. `free-search search`: "backtesting mean reversion range breakout strategy best practices survivorship bias 2026" -> Fortraders bias taxonomy (5 biases), QuantNeuralEdge WF guide, ORB 400% claim, survivorship 5-15%/yr inflation.
3. `searxng suggestions`: "PVD PBD fair value range breakout confirmation trading" -> no suggestions (logged as null signal).
4. `searxng web_search`: "Market Profile Value Area fair value range trading strategy futures" -> NETWORK ERROR (SearXNG URL unreachable; fallback to other tools — logged honestly).
5. `openresearch web_search`: "Robbins World Cup trading championship futures verification rules" -> entry agreements, real-money % return ranking, divisions.
6. `openresearch search_openalex`: "range breakout false breakout confirmation mean reversion futures" -> Alqaydi (2026) Value Area harvesting SSRN; theses on ANN/technical analysis.
7. `paper-search search_arxiv`: "intraday range breakout backtest futures market microstructure" -> Maier-Paape backtest-engine correctness (2015), LOB dynamics (2025), Polymarket microstructure (2026).
8. `paper-search search_papers` (semantic/openalex/crossref): "false breakout liquidity sweep mean reversion backtest" -> Mesfin (2026) MNQ falsification 0/14 (key benchmark), Nikolopoulos spurious predictability, Perera SOL profile Tape-Speed Sharpe>2, Arda Bollinger regimes.
9. `duckduckgo_search`: "DAX futures backtest yahoo finance GDAXI intraday data free" -> Yahoo ^GDAXI, FDAX replay tools, futures specs.
10. `agent-reach_search web`: "volume profile value area trading strategy backtest results" -> truncated 61KB (logged, not cherry-picked; delegated to avoid context bloat).
11. `wiki_search`: "Market profile trading strategy" -> Day trading / Walk-forward / Price action / Global macro (context).
12. `kaggle datasets_list` ("dax futures intraday"): ERROR sort_by type (logged).
13. `kaggle search_everything` ("futures backtest mean reversion"): crude oil 20yr dataset, Nifty/precious-metals notebooks.
14. `gitmcp search_generic_documentation` (freqtrade backtesting): SOCKET CLOSED (logged).
15. `openresearch hacker_news`: "backtesting trading strategy overfitting" -> PyBroker, forex data threads.
16. `gsd_websearch`: "futures trading strategy verification walk-forward out-of-sample 2026 best practice" -> empty (logged).
17. `superpowers semantic_search_skills`: "backtesting research reproducibility docker" -> writing/testing skills (method note).
18. `openresearch stackoverflow`: "yfinance download DAX intraday backtest python" -> no results (logged).
19. `free-search search`: "Sharpe ratio profit factor maximum drawdown trading strategy evaluation 2026" -> Wyckoff/AlgoVerdict/LuxAlgo/Tradewink metric guides (Sharpe+MaxDD+PF triad).

Voting synthesis: web + academic + practitioner + community sources converge on same verification triad (bias control + WF + friction) and same caution (naive breakouts fail costs). No source claims PVD secrets; all respect undisclosed zone rules. This repo implements that consensus.
