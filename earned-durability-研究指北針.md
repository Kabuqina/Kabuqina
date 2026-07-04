# 掙來的持久性 — 研究指北針

### Earned Durability: Treating Side Effects as First-Class Citizens in LangGraph Agent Harnesses

> **這張卡的用途**：帶進 Cowork，對著 Kabuqina 的實際程式碼逐條盤問。
> 不是提綱，是尺。每次想偏題，回到第 0 節那三行擋回去。

---

## 0. 定錨（偏題時看這裡）

- **工作標題**：掙來的持久性 / *Earned Durability*
  （定稿留到對照實驗做完再回頭改——很可能那時就改不動了，因為它已經對了。）

- **主幹（一句劃死）**：在 LangGraph 裡，durability 不是 checkpointer 給的屬性，是妳*把副作用切成正確的可重放單位*掙來的。切錯了，state 回滾而世界不回滾，agent 就在一個可預測的地方壞。證完，收。

- **種子（一句劃死，只點到不展開）**：即使副作用處理對了，LangGraph 仍只給了 OS 的一半——它保存 context，但不保證 liveness。補上 supervisor 那半邊，是更大型 agent 的下一個結構問題（＝北極星那篇的開頭）。

- **擋偏題的咒語**：任何往 supervisor / multi-agent / agent-as-kernel 飄的衝動——「那是北極星那篇的肉，不是這篇的。」

---

## 1. 核心命題（stable 的那層，不隨 model 過期）

沿著一把刀劈開 harness：

- **Cognition（認知）半**：替 model 補腦的 scaffold（task decomposition、reasoning 拐杖、因單模型不夠而拆的 multi-agent）。存在理由 =「model 現在還不行」。→ **temporary，寫成隨時能撕的形狀。**
- **Boundary（邊界）半**：調解「計算 ↔ 世界」的層——失敗、外部狀態、時間、其他 agent。→ **stable，押重注。**

判準（對 harness 每一塊都問一次）：

> **「如果明天 model 變強 10 倍，我還要不要這塊？」**
> 要 → infrastructure / governance / economics 撐起來的，stable。
> 只因「model 現在不行」才在 → temporary。

為什麼 boundary 半 model-proof：它調解的是計算與世界的**邊界**（時間、失敗、外部狀態），這些是物理不是智力；更聰明的 model 只改善 reasoning，碰不到 boundary。**邊界不會變聰明。**

---

## 2. 三條裂縫（＝三個 boundary 面，已用官方 docs / issue 坐實）

| 裂縫        | boundary 面 | LangGraph 現狀（已查證）                                                                                                                                                             | 生出的設計原則                            |
| --------- | ---------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------- |
| **一**     | 失敗         | checkpoint 落在 super-step 邊界，node 內部黑箱；resume 從**該 node 開頭整個重跑**。「pending writes」語義：同一 super-step 已成功的 sibling node 不重跑。內建 `RetryPolicy`/`TimeoutPolicy`/`error_handler`（1.x）。 | durability 是切對可重放單位換來的，不是免費屬性。     |
| **二（主幹）** | 外部狀態       | **官方明定**：resume 時 checkpoint 之後的 node 整個重跑，含 LLM call、API request，全部重新觸發。解法：副作用包進獨立 `task`，重放時從持久層取回、不再執行；用 idempotency key / 先驗證既有結果去重。                                      | **state 回滾，世界不回滾。副作用要當一等公民設計。**    |
| **三**     | 時間         | **官方未解**：GitHub issue 明言 LangGraph 目前無內建機制偵測/管理 state schema 隨時間的不相容演化；schema 一改，睡著的舊 checkpoint 醒來就炸，rollback 也踩雷。                                                           | 長命的暫停會撞上演化；時間是要被設計的維度。（此篇只點到，不主攻。） |

---

## 3. 那把「第二刀」（種子的精確形狀）

搜證逼出的升級：**「有 checkpointer」≠「有 durable execution」。**

LangGraph 給的是 OS 的 **「saved context + syscall 語義」** 半：

- `checkpoint` = process context（PCB）
- `interrupt()` = **跨人類邊界的 blocking syscall**（主動 yield，不是硬體中斷——paper 裡值得校正這個命名）

LangGraph **不給**的另一半 = 讓 process「活著」的東西：

- 失敗偵測（沒有 supervisor / watchdog / heartbeat；崩了沒人知道，直到妳本人發現）
- 自動 resume（要妳自己 `invoke(None, config)` 帶對 thread_id）
- 單一執行保證（兩個 process 同時 resume 同一 thread_id，LangGraph 不擋，要自己做 distributed lock）

→ 完整 harness = **LangGraph 半（durable state + syscall）＋ 自己補的 supervisor 半（liveness）**。
這是 boundary 半邊內部的**第二刀**：分「state 持久化」（LangGraph 給）vs「liveness 保證」（LangGraph 不給）。Temporal / Dapr 補的正是後者。

---

## 4. 對 Kabuqina 的四問（Cowork 調研主清單）

拿主幹去掃 repo，逐條回答、貼證據（檔案路徑 + 行號）：

1. **副作用清單**：harness 裡哪些動作*不可回滾*地改動外部世界？
   
   - 候選：PPTX 落檔、寫學生檔案、Python 執行的檔案 I/O、外部 API 呼叫……
   - 產出：一張「副作用清冊」——這就是裂縫二的實驗素材庫。**PPTX 產出最肥**（不可回滾又看得見）。

2. **重放邊界對齊**：那 **21 條 exit contract** 是不是天然的「可重放單位」邊界？和 LangGraph 的 super-step / node 邊界對得齊嗎？
   
   - ⚠️ **最關鍵**。粒度錯位處 = 天真版會壞的點 = paper 第一手材料。

3. **現在誰在兜底**：要被換掉的**同步 ReAct loop**，目前怎麼處理「跑到一半掛掉」？
   
   - 若答案是「沒處理、整個從頭來」→ 它就是天真版的**活體樣本**，不用另造。

4. **遷移即案發現場**：Phase 3.5 從同步 loop → LangGraph，這個「換」本身會不會製造裂縫二？
   
   - 舊 loop 裡的某個副作用，搬進 LangGraph node 後，因 node 重放語義而**變成會重複執行**？
   - 遷移過程本身就是裂縫二的天然實驗。

---

## 5. 對照實驗骨架（裂縫二為主幹）

論證靠**對照**，不靠正面示範。每條原則：先讓天真版*真的壞給妳看*，再讓原則版壞消失。

**裂縫二（主攻）**

- 天真版：一個有副作用的動作（挑 PPTX 落檔）直接寫在 node 裡；製造一次 node 重放 → 觀察檔案被產第二次 / 狀態與世界不一致。
- 原則版：副作用包進 `task` + idempotency key（或先驗證既有結果）→ exactly-once 成立。
- ⚠️ 設計陷阱：天真版要**明確關掉/繞開**內建 `RetryPolicy` 等保護，否則框架默默兜底，對照會糊。

**裂縫一（帶出來，不主攻）**

- 天真版：一個 node 內部多步副作用，中途 crash → resume 後狀態錯亂 / 重複。
- 原則版：切成正確可重放單位 → crash-resume 乾淨。

**裂縫三（只點到）**

- 描述性帶過 + 指向未解 issue，當結尾種子的一部分。

---

## 6. 學術錨點（真貨；精確 cite 前需釘死作者/出處/年份）

- **Sagas** — Garcia-Molina & Salem, 1987。裂縫二補償機制鼻祖（副作用回滾不了、只能補償）。
- **Crab checkpoint/restore study, 2026** — >75% 的 agent turn 不產生恢復相關 state；semantics-aware 法把恢復正確率 8%→100%、checkpoint 流量 −87%。裂縫一「該存什麼/不該存什麼」的實證彈藥。
- **Durable Functions / Temporal** — replay-based durable execution 的成熟參照，supervisor 半邊的樣板。
- **Pregel（BSP / super-step, 2010）** — 解釋 checkpoint 邊界為何落在 super-step 之間。
- **Orthogonal persistence / single-level store（KeyKOS / EROS 一脈）** — 「執行中＝已保存」極限理想的 OS 史根，OS 類比的坐實。

> ⚠️ **cutoff 提醒**：LangGraph 的*當前*版本行為（重放觸發條件、durability mode 語義、functional API 的 durability 保證、schema 演化有無新解）變很快，超過 Jan 2026。寫進 paper 當事實前，逐條重新查證、標註查證日期。

---

## 7. 下一步（二選一，Cowork 用）

- **Top-down**：先把官方 durable-execution docs ＋〈durable execution 如何燒到你〉讀完，讓裂縫二的天真/原則版在腦中長出具體形狀，再對 repo。
- **Bottom-up（建議）**：直接在 Kabuqina 挑 PPTX 產出這個現成副作用，手刻一個會重複產檔的天真版，從髒現場往上長。妳每天在跟這個副作用搏鬥，比想像一個更生猛。

---

*工作標題，非定稿。全文寫完才知道實際證明了什麼。*

---
---

# 附錄 A — 基礎調研備忘（2026-07-03 完成，Cowork 回填）

> 這一段是把第 4/6 節的「待查證」逐條打勾。每條都附證據來源（repo 檔案:行號，或外部出處＋查證日）。
> 指北針上半段（第 0–7 節）不動；下半段是它的填空。

## A.0 一句話結論（調研之後主幹沒變，反而更硬）

Kabuqina 現在正**卡在裂縫二的門口**——Phase 3.5 把同步 ReAct loop 換成 LangGraph `StateGraph`，但**刻意不裝 checkpointer**（`DECISIONS.md:250`）。所以此刻它擁有「可回滾的 state 語義」的**形狀**，卻還沒承擔「世界不回滾」的**代價**。這讓它成為主幹論證的完美活體：副作用清冊已經被工程本身列成 `ExitPolicy` 六旗標，重放邊界之爭已經被寫成「21 條 exit ≠ 8 個 graph node」的粒度錯位，而「工具已執行就不能重跑」已經被寫進 dispatcher 的硬規則。**論文不需要製造天真版——遷移計畫自己把天真/原則的張力顯影了。**

---

## A.1 對 Kabuqina 的四問（第 4 節主清單）——已回答

### Q1 · 副作用清單 → 已列，且工程已經替妳分類

harness 裡不可回滾地改動外部世界的動作，證據集中在兩層：

**(a) 每個 turn 結束時的六類副作用**，已被凍結成一個 TypedDict：
`hermes_core/agent/graph_engine/contracts.py:52-64` 的 `ExitPolicy` —
`cleanup_task_resources` / `persist_session` / `save_trajectory` / `fire_post_llm_call` / `fire_on_session_end` / `clear_interrupt`。
這六個就是「一個 turn 收尾時對世界做了什麼」的窮舉。加上六個 load-bearing plugin hook（`on_session_start`/`pre_llm_call`/`pre_api_request`/`post_api_request`/`post_llm_call`/`on_session_end`，見 replatform plan「Grounded loop facts」）。

**(b) 工具執行本身**——真正不可回滾、看得見的那類。旗艦是 **PPTX 落檔**（指北針早判斷對了：「最肥」）：
`hermes_core/tools/document/pptx_writer.py:376` `pptx_write()`。它的副作用**不是單步而是三步鏈**：
1. 透過 `callback(question, [], kind="pptx_render", artifact=...)` 向 webview 發一個渲染互動（`pptx_writer.py:439`）——這是一次**跨人類/跨進程邊界的 blocking 呼叫**，語義上就是第 3 節說的 `interrupt()`＝syscall；
2. 收回 base64 的 .pptx bytes（`:461`）；
3. 解碼後寫進 workspace-validated 路徑（`:471` `base64.b64decode` → `:475` `_validate_write_path` → 落盤）。
**沒有 idempotency key、沒有 already-exists 去重、沒有 overwrite 守衛**（`document_tools.py` 搜 `idempotent|already exists|dedup` 皆無命中）。→ 一旦這步落在會重放的單位裡，重放＝重新彈 UI＋重新產檔。**這就是裂縫二的實驗素材，現成的。**

其他候選副作用（次肥）：`session_db` 持久化（`DECISIONS.md:250` 明載它是唯一 conversation store）、trajectory 落檔（`_save_trajectory`，`DECISIONS.md:277`）、`deliverable_contract.py` 主導的學生 deliverable 產出（`tools/deliverable_contract.py`，planner↔writer 共用詞彙表）。

### Q2 · 重放邊界對齊 → ⚠️ 最關鍵的一問，答案是「天然錯位」

那「21 條 exit contract」**確有其物**，且比指北針記的更精確：
- 它們是 `AIAgent.run_conversation` 的 **21 個 source-level return 點**（`run_agent.py`，該函式當時橫跨 9374–12664 行，全檔 12,897 行；replatform plan「Grounded loop facts」）。
- reachability spike（`docs/superpowers/specs/2026-06-28-phase-3.5-exit-reachability-spike.md`）把 21 拆成 **19 個 runtime 可達 + 2 個結構性不可達**（10530、10542 兩個 truncation fallthrough，因為兩個 live normalizer 永不回傳 `None`）。
- 完整清單在 `test_exit_contract.py` 的 21 列 scenario inventory（replatform plan Task 2 Step 3），從 `nous_rate_guard_without_fallback` 到 `normal_final_result`，**以 source 順序**用 AST 綁定 return 行號。

**粒度錯位坐實在這裡**：
- LangGraph 這半只有 **8 個 route/node**：`prepare_request` / `call_transport` / `process_response` / `handle_transport_error` / `dispatch_tools` / `apply_steer` / `summarize_on_budget` / `finish`（`contracts.py:38-47`）。
- 21 個 legacy exit **全部塌縮進 `finish` 這一個 node**，由它套一組 `ExitPolicy`（`nodes.py:93-96` → `apply_exit_policy`）。
- 於是「可重放單位」（super-step / node 邊界）與「語義退出單位」（21 個 return）**根本不是同一把尺**。super-step 邊界落在 node 之間（Pregel BSP 的遺傳，見 A.3），而 21 個退出是 node **內部**的語義分叉。

**更尖的證據——錯位不是我推的，是工程自己踩到的**：`DECISIONS.md:256-283` 的「graph-engine parity follow-ups」記錄了 Task 4–7 只達到 **core-result parity** 卻漏掉一堆 **side-effect parity**（PH35-FU-001…009）：hook 沒在同邊界發、session usage 沒累加、trajectory 沒寫、**早退出的 cleanup/persist/interrupt-clear 不一致**。這正是「state 對了、世界沒對齊」在真實 code review 裡的長相。其中 `DECISIONS.md` decision 4（replatform plan「Status and decisions」）白紙黑字：**「current early returns do not all execute cleanup, post_llm_call, or on_session_end. That inconsistency is part of the characterization contract.」**——21 個退出對副作用的處置**本來就不齊**。這就是天真版會壞的點，不用另造。

### Q3 · 現在誰在兜底 → 沒人，且他們知道沒人

要被換掉的同步 ReAct loop = `run_agent.py` 裡被保留、改名為 `_run_conversation_loop` 的舊 body（replatform plan Task 10；`DECISIONS.md:304-320`）。它「跑到一半掛掉」怎麼辦？——**沒有自動 resume**：`DECISIONS.md:250` 明載 Phase 3.5 不裝 checkpointer，`session_db` 是唯一持久層；掛了就靠使用者本人重開。這對齊第 3 節「LangGraph 不給的另一半＝liveness」：崩了沒人知道、沒有 watchdog/heartbeat、沒有 single-execution 保證。→ 舊 loop 就是天真版的**活體樣本**。

### Q4 · 遷移即案發現場 → 是，且工程用一條硬規則擋住了它

Phase 3.5 從同步 loop → LangGraph，這個「換」本身**會不會製造裂縫二？** 會——而且工程**明確意識到並立規矩擋**：

- replatform plan decision 5：**「Never live-shadow side effects… never automatically rerun a failed graph turn through the loop after a tool may have executed.」**
- Task 10 落地版（`DECISIONS.md:313-316`）：public `run_conversation` 變成 thin dispatcher，「selects graph or loop **before any per-turn side effect** and **never falls back across engines mid-turn** (a post-tool graph failure returns its own error rather than re-running the loop and duplicating effects)。」

**這就是裂縫二的定理，被寫成了一條生產守則。** 一個工具（如 `pptx_write`）一旦執行，engine 就不能假裝什麼都沒發生、換條路重跑——因為 state 能回滾，那份 .pptx 不能。論文的主幹命題在 Kabuqina 這裡不是假說，是已經被工程用「禁止跨引擎中途 fallback」買單的既成事實。

---

## A.2 LangGraph 現行行為（第 6 節 cutoff 提醒）——2026-07-03 重新查證

指北針警告「LangGraph 當前版本行為變很快，超過 Jan 2026」。已重查，關鍵更新：

- **Durability 現在是一個顯式 mode，三檔**（2025 年中引入；官方 docs〈Durable execution〉）：
  `"exit"`（最快，只在結束時 checkpoint）／`"async"`（下一步執行時非同步寫，崩潰有小機率漏寫）／`"sync"`（每步前同步寫，最durable、有 overhead）。→ 指北針裡「durability mode 語義」這格現在有明確三值可 cite。查證日 2026-07-03。
- **StateGraph resume 起點**：官方明述「resumption 從**執行停止的那個 node 的開頭**起」；subgraph 則回到呼叫它的 parent node。**完全坐實裂縫二**——node 內部整段重跑。
- **Functional API 的原則版就是官方解法**：`@entrypoint` / `@task` 兩個 decorator；官方明講「把**有副作用或非確定性的操作包進 `@task`**，好讓 workflow 重放時這些操作**不被重複執行**」。checkpoint 在每次 entrypoint 執行後產生。→ 指北針第 5 節「原則版：副作用包進 `task`」**與官方措辭逐字對上**，這是強背書，不是我的發明。
- **Kabuqina 用的是 low-level `StateGraph`（`langgraph==1.2.6`），不是 Functional API**（`DECISIONS.md:248`）。所以「把副作用包進 task」這個官方原則，Kabuqina **還沒享受到**——它手動在 `finish`/`ExitPolicy` 裡管，這反而讓論文的對照更乾淨（可對比 low-level 手管 vs functional API 自動化）。
- **Schema 演化**：仍未見官方內建解（維持指北針裂縫三的判斷）；只點到、不主攻。

外部佐證（可入 related work / 動機）：Diagrid〈Why Checkpoints Aren't Durable Execution〉、Medium〈The Hidden Replay Risk in LangGraph〉——都在講「有 checkpoint ≠ durable execution」，與第 3 節「第二刀」同一刀口。

## A.3 學術錨點——精確出處已釘死（可直接進 references）

| 錨點 | 精確 cite（查證日 2026-07-03） | 對論文的作用 |
| --- | --- | --- |
| **Sagas** | Garcia-Molina & Salem, *Sagas*, ACM SIGMOD 1987, **DOI 10.1145/38713.38742**（SIGMOD Record 版 10.1145/38714.38742）。Princeton。 | 裂縫二鼻祖。關鍵措辭已核："compensating step **undoes—from a semantic point of view**—the step, but does **not necessarily return the database to the state that existed when the step began**." ← 這就是「世界不回滾成一模一樣，只能語義補償」的原始出處。 |
| **Crab** | *Crab: A Semantics-Aware Checkpoint/Restore Runtime for Agent Sandboxes*, **arXiv:2604.28138**, 2026-04-30。 | 裂縫一「該存什麼」的實證彈藥，數字已核：>75% 的 agent turn 不產生 recovery-relevant state；recovery correctness **8%→100%**；checkpoint 流量 **−87%**；within **1.9%** of fault-free；評測於 Terminal-Bench + SWE-Bench。 |
| **Durable Functions / Temporal** | Azure Durable Functions（replay-based，event sourcing，append-only history，orchestrator 必須 deterministic — MS Learn〈Durable orchestrations〉〈code constraints〉）；Temporal（同一 replay 模型，由前 AWS SWF＋Azure DF 架構師打造）。 | supervisor 半邊（liveness）的成熟樣板。註：它們的「deterministic + 把 side effect 隔進 activity/task」正是 LangGraph `@task` 的前輩。 |
| **Pregel** | Malewicz et al., *Pregel: A System for Large-Scale Graph Processing*, SIGMOD 2010, **DOI 10.1145/1807167.1807184**。源自 Valiant 的 BSP。 | 解釋 checkpoint 邊界為何落在 super-step 之間＝LangGraph node 邊界的血統，直接支撐 Q2 的粒度錯位論證。 |
| **Orthogonal persistence / single-level store** | EROS（Shapiro & Smith, *EROS: a fast capability system*, SOSP 1999 / SIGOPS OSR 33(5), **DOI 10.1145/319344.319163**）；KeyKOS（自 1983 生產使用，system-wide 背景 checkpoint）。 | 「執行中＝已保存」極限理想的 OS 史根，坐實第 3 節 OS 類比。main memory 視為 single-level store 的 cache。 |

---
---

# 附錄 B — 論文 structure 提案

> 三種顆粒度：先給一句話骨架，再給節構成（含每節主張與所需證據），最後給寫作順序建議。
> 原則：**論證靠對照**（第 5 節），所以 structure 的重心壓在「案例＋對照實驗」，理論框架只夠撐起它。

## B.0 骨架（一句話一節）

I 引言：durability 是掙來的，不是 checkpointer 給的 → II 那把刀：cognition/boundary，model-proof 判準 → III 三條裂縫：失敗/外部狀態/時間 → IV 第二刀：有 checkpointer ≠ durable execution（OS 類比）→ **V 案例：Kabuqina 四問**（第一手主體）→ **VI 對照實驗：PPTX 天真 vs 原則**（主攻裂縫二）→ VII related work → VIII 限制＋種子（裂縫三＋supervisor 半＝北極星）→ IX 收。

## B.1 節構成（建議 8+1 節）

**1. 引言 — 命題與代價**
主張：在 LangGraph 裡，durability 不是 checkpointer 給的屬性，是把副作用切成正確可重放單位掙來的；切錯 → state 回滾而世界不回滾，agent 在可預測處壞。
放：主幹一句（第 0 節）、一個一句話的 PPTX 誘因（重放產第二份檔）當 hook。**證完即收的承諾寫在這**。

**2. 一把刀：cognition 半 vs boundary 半**
主張：harness 可沿「補腦 vs 調解計算↔世界」劈開；前者 temporary（model 變強就撕），後者 stable（邊界不會變聰明）。
放：第 1 節的 model-proof 判準（「明天 model 強 10 倍還要不要這塊？」）。這節定義全文只押 boundary 半。

**3. 三條裂縫（boundary 的三個面）**
主張：失敗、外部狀態、時間三面各生一條裂縫與一條設計原則。
放：第 2 節的表（已用官方 docs 坐實），**A.2 的三檔 durability mode + StateGraph resume 起點**補進「現狀」欄。明確標：本篇主攻裂縫二，裂縫一帶出、裂縫三只點到。

**4. 第二刀：有 checkpointer ≠ durable execution**
主張：LangGraph 只給了 OS 的一半（saved context + syscall 語義），不給 liveness（失敗偵測/自動 resume/單一執行保證）。
放：第 3 節的 OS 類比（checkpoint=PCB，`interrupt()`=跨人類 blocking syscall——並校正命名：是主動 yield 不是硬體中斷）。related 佐證：Diagrid / Medium 兩篇（A.2）。**Temporal/Durable Functions 在此作為「補上另一半」的樣板**點名，細節留到 VII。

**5. 案例研究：Kabuqina harness 四問 ★ 論文主體上半**
主張：一個真實 agent harness 站在裂縫二門口時，副作用/重放邊界/兜底/遷移各長什麼樣。
四小節直接對應 A.1 的 Q1–Q4，每小節掛 file:line 證據：
- 5.1 副作用清冊：`ExitPolicy` 六旗標 + `pptx_write` 三步鏈（Q1）
- 5.2 粒度錯位：21 exit vs 8 node，塌縮進 `finish`；用 PH35-FU-00x 的 side-effect parity 漏洞當「錯位在 review 裡的實況」（Q2）——**這節是全文最尖的一手材料**
- 5.3 沒人兜底：無 checkpointer、無 watchdog，舊 loop = 活體天真版（Q3）
- 5.4 遷移即案發現場：dispatcher「副作用前選定引擎、禁止跨引擎中途 fallback」= 裂縫二被寫成生產守則（Q4）

**6. 對照實驗：PPTX 落檔，天真 vs 原則 ★ 論文主體下半（主攻裂縫二）**
主張：讓天真版真的壞給妳看，再讓原則版把壞消掉。
放：第 5 節的實驗骨架。
- 天真版：`pptx_write` 直接寫在會重放的單位裡 → 製造一次 node 重放 → 觀察檔案被產第二次 / state 與世界不一致。**設計陷阱寫進方法論**：要明確關掉/繞開內建 `RetryPolicy` 等保護，否則框架默默兜底、對照糊掉。
- 原則版：副作用包進 `task` + idempotency key（或先驗證既有結果）→ exactly-once。**明確對照 Kabuqina 現用 low-level StateGraph 手管 vs Functional API `@task` 自動化**（A.2）。
- 帶出裂縫一（不主攻）：node 內多步副作用中途 crash → resume 後錯亂；引 Crab 數字說「多數 turn 根本不該存」。

**7. Related work**
主張：把命題接上 40 年的譜系，證明「邊界問題是物理不是智力」不是新話術。
放：A.3 五個錨點——Sagas（補償）、Pregel（super-step 邊界血統）、EROS/KeyKOS（orthogonal persistence 的極限理想）、Durable Functions/Temporal（liveness 樣板）、Crab（agent 時代的實證）。

**8. 限制與種子（裂縫三 + supervisor 半）**
主張：即使副作用處理對了，LangGraph 仍只給 OS 一半；補上 supervisor（liveness）是更大型 agent 的下一個結構問題。schema 演化（裂縫三）是尚未被設計的時間維度。
放：第 0 節種子一句 + 裂縫三指向未解 issue。**明講這是北極星那篇的開頭，不是這篇的肉**（擋偏題咒語內建進結尾）。

**9. 結論**
回收引言的承諾：主幹證完。一句話重述「durability 是掙來的」，停。

## B.2 寫作順序建議（≠ 閱讀順序）

先寫 **5 + 6**（一手材料最硬、最會在寫的過程中改變妳對主張的理解，第 134 行那句「全文寫完才知道證明了什麼」就是指這個）→ 再寫 **3 + 4**（理論框架，此時已知實驗要它撐什麼）→ 回頭寫 **1 + 2**（引言最後定稿，因為它承諾的正是妳已證的）→ **7 + 8** 收邊 → **9**。附錄 A 的證據表可直接當 5/7 節的素材庫。

## B.3 兩個尚待妳拍板的縫（我沒替妳決定）

1. **對照實驗要不要真跑，還是走 code-archaeology？** 現況給了第三條路：Phase 3.5 的 `test_graph_differential_sequences` + PH35-FU-009 的「22 個 graph-specific 等價落差」已經是半個現成對照。可以「真跑一個 PPTX 重放」+「引用既有 differential 證據」混合，省一半力氣。
2. **命名校正的份量**：`interrupt()`＝syscall 這個校正（第 3 節）要當一句 footnote，還是升成第 4 節的一個小論點？它其實是 OS 類比是否成立的關鍵接縫，我傾向升格，但這改主張重心，留妳定。

---

*附錄 A/B 由 Cowork 於 2026-07-03 回填。上半段指北針未動。所有 repo 證據為當日 HEAD；所有外部出處標查證日，寫進 paper 當事實前請依第 6 節 cutoff 提醒再核一次版本。*

---
---

# 附錄 C — agent-durability 引文叢（從 Crab 往外爬一層，2026-07-03）

> 方法：以 Crab（arXiv:2604.28138）為種子，沿 Semantic Scholar / arXiv 鄰接往前後各爬一層，
> 收 2025H2–2026H1 的 agent 可恢復性子領域。**全部是 preprint，引用前逐條核 venue 與數字**（第 6 節 cutoff）。
> 分層＝閱讀優先序：C.1 直接站在主幹上，C.5 是產品文件只作動機。

## C.1 主幹核心（直接站在裂縫二／一，優先讀）

| 文獻 | arXiv id · 日期 | 對本文的作用 | 可信度 |
| --- | --- | --- | --- |
| **Atomix: Timely, Transactional Tool Use for Reliable Agentic Workflows** | 2602.14849 · 2026-02-16 | **補妳最大的引用空洞**：progress-aware transactional semantics for tool calls＝裂縫二「exactly-once 副作用」的正面學術解法。Max Planck (MPI-SWS)＋EPFL＋Aarhus，Bindschaedler 組。 | 有 OpenReview forum（投稿中，比裸 preprint 稍受檢驗）。★最推 |
| **Recoverability Has a Law: The ERR Measure for Tool-Augmented Agents** | 2601.22352 · 2026-01-29 | 把 recoverability 形式化成 **Expected Recovery Regret**（恢復策略偏離最優的量）。裂縫一「該恢復到哪／存什麼」的理論骨架，替 Crab 的實證數字提供 measure。 | preprint，先核定義自洽 |
| **Crab: A Semantics-Aware Checkpoint/Restore Runtime for Agent Sandboxes** | 2604.28138 · 2026-04-30 | 已用（附錄 A.3）。裂縫一實證彈藥。 | 已核數字 |
| **DART: Semantic Recoverability for Structured Tool Agents** | 2605.23311 · 2026-05-22 | Crab 的語義補集：structured tool agent 的 semantic recoverability。可與 Crab 對照「host-side 透明 vs agent-structure-aware」兩條路線。作者群含上海交大／上海 AI Lab。 | preprint |

## C.2 checkpoint/restore 機制叢（裂縫一機制面，選讀）

| 文獻 | arXiv id · 日期 | 作用 |
| --- | --- | --- |
| **DeltaBox: Scaling Stateful AI Agents with Millisecond-Level Sandbox Checkpoint/Rollback** | 2605.22781 · 2026-05 | CRIU image chain＋template pool 做毫秒級 rollback。機制面對照組；證明「rollback 便宜」不等於「rollback 正確」——正好反襯妳的主幹。 |
| **ACRFence: Preventing Semantic Rollback Attacks in Agent Checkpoint-Restore** | 2603.20625 · 2026-03 | semantic rollback **攻擊**（restore 後重放 tool call 造成 credential reuse 等）。可進「限制／威脅模型」節——說明重放安全不只是正確性還是安全性問題。 |

## C.3 provenance / trace（裂縫二的觀測面，related work 省力）

| 文獻 | arXiv id · 日期 | 作用 |
| --- | --- | --- |
| **From Agent Traces to Trust: A Survey of Evidence Tracing and Execution Provenance in LLM Agents** | 2606.04990 · 2026-06 | **survey**——related work 的省力入口，一次接上 provenance 這條線。 |
| **TRACER: Verifiable Generative Provenance for Multimodal Tool-Using Agents** | 2605.09934 · 2026-05 | verifiable provenance；若妳談「怎麼知道副作用發生過」可引。 |

## C.4 可靠性／例外／並發（周邊，判斷是否納入）

| 文獻 | arXiv id · 日期 | 作用 |
| --- | --- | --- |
| **Atomix 之外的交易線索見 C.1** | — | — |
| **CoAgent: Concurrency Control for Multi-Agent Systems** | 2606.15376 · 2026-06 | 並發控制＝第 3 節「single-execution 保證」那半的直接前沿。**接北極星（supervisor 半）最順的一篇。** |
| **Sherlock: Reliable and Efficient Agentic Workflow Execution** | 2511.00330 · 2025-11 | 可靠 workflow 執行；周邊對照。 |
| **Self-Healing Agentic Orchestrators for Reliable Tool-Augmented LLM Systems** | 2606.01416 · 2026-06 | liveness／自癒；北極星素材。 |
| **SHIELDA: Structured Handling of Exceptions in LLM-Driven Agentic Workflows** | 2508.07935 · 2025-08 | 結構化例外處理；與失敗（裂縫一）相關。 |
| **Get Experience from Practice: LLM Agents with Record & Replay** | 2505.17716 · 2025-05 | record & replay 的 agent 版；注意它的 replay 是「經驗重用」不是「故障恢復」，別跟妳的 replay 混。 |

## C.5 工業系統（產品文件／公告，只作動機與 related，非學術份量）

- **Temporal**（replay-based durable execution，前 AWS SWF＋Azure DF 架構師）——supervisor 半樣板，已在附錄 A.3。
- **Azure Durable Functions**（event sourcing / deterministic orchestrator）——已在 A.3。
- **AWS Lambda Durable Functions**（2025-12 公告：steps/waits/checkpoints/replay/retries/long suspensions）——雲廠商跟進的時間戳，適合放「產業正在收斂到 durable execution」的動機句。
- **Hatchet**（durable tasks＋durable event log）、**DBOS**（DB-backed workflow/step state，含 OpenAI Agents 整合）——輕量 durable-execution 實作對照。
- **OpenAI Agents SDK**（2026-04 更新：externalized state / snapshotting / sandbox-aware orchestration / rehydration）——大廠把 durability 收進 SDK 的信號。

## C.6 檢索方法與 meta 資源（給後續自己爬）

- **引文圖擴張**：以 **Atomix (2602.14849)** 和 **Crab (2604.28138)** 為雙種子，在 **Connected Papers** 或 **Semantic Scholar** 跑 "cited by / references"，這叢應該會收斂——上面 C.1–C.4 多數就是這兩顆的鄰居。
- **meta 清單**：GitHub `VoltAgent/awesome-ai-agent-papers`（2026 agent 論文策展，含 workflows/reliability 分類），可當每月掃新的入口。
- **preprint 紀律**：C.1–C.4 全是 2025H2–2026H1 preprint。引用前 (a) 查是否已進 venue（Atomix 已有 OpenReview）、(b) 用最新版本號、(c) 要引的數字回原文核。arXiv id 前四碼＝YYMM，可一眼判新舊。
- **仍缺的兩塊正典**（附錄 A.2「引用空洞」裡點過，這輪 agent 叢補不了，要往經典找）：event sourcing / WAL 的正典（如 ARIES）與 exactly-once/at-least-once 的訊息傳遞經典——這兩塊 agent preprint 都預設妳懂，論文要自己往 DB/分散式系統 canon 補。

---

*附錄 C 由 Cowork 於 2026-07-03 補。全部為 arXiv preprint，日期依 arXiv id（YYMM）標註；作者/venue 僅核了 C.1 兩篇主推，其餘引用前請自核。*
