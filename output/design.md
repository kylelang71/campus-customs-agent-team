# Dashboard Design

This note explains why the agent dashboard looks and behaves the way it does.

## The idea: a desk

I built the board around a desk. The tickets, the to-dos, sit physically on the desk in front of the person, like papers waiting to be handled. Picking one up and handing it to the agent team is the one thing the human does to start work. Nothing runs on its own.

## Where the information goes: the backsplash

Once a ticket has been delegated to the agent team, the information starts to build up, the way work piles up on a desktop. But there is no desktop here. Instead, the information builds up on the backsplash of the desk, the wall behind it. Selecting a ticket pins its summary there: the request and a timeline of what each agent received, used, asked and said. The desk is for what the person has to do, and the wall is for what the team has done.

## Making it worth looking at

My first iteration was relatively boring and bland. A page of cards and text is accurate, but nobody wants to watch it. So I added background imagery to make it interesting to look at, something that Yale SOM students would find interesting: a window at the top of the page looking out over the skyline of New York City, with the Chrysler Building, the Empire State Building and One World Trade Center. It makes the board feel like a real place to work.

## The agents pop out of the backsplash

I had the agents pop out of the top of the backsplash, peeking up over the sill in front of the window, and I gave them interactive visual features to show that work was going on, and which agent was doing what work at what time. Without this, it was really unclear whether any work was being done at all, and how it was being done.

The agents are small, flat robots, clean and minimal rather than cartoonish. Each has its own shape and colour so they can be told apart, and a name tag that says what it is doing:

- **Idle:** dim eyes and slow breathing. It has no task.
- **Working:** bright blue eyes, a pulsing light and a moving voice bar. It is working on its own. If it has been quiet for a while, its name tag says so. Every running agent also shows a small pulsing heart on its name tag with what it is doing and for how long, so a long wait on the model reads as "alive and waiting", not as a glitch.
- **Passing information:** two robots turn toward each other, turn violet, and a dashed line with a moving dot runs between them while a task or an answer changes hands. A blue line shows one agent checking in on another.
- **Waiting:** an amber light and bouncing dots, with a dotted arrow to the teammate it is waiting on. A robot only shows as waiting while someone it asked is still working, so the board never shows everyone waiting.
- **Hovering** the cursor over a robot makes it hop, so the board feels alive.

## The rest of the desk

- The **checking balance** sits on the desk and drops when a payment is approved.
- **Approvals** are sticky notes: payments, purchase orders and customer messages. Agents only prepare them; a person approves them by name, and that is the only thing that changes cash. A payment or order the checking balance can't cover can't be approved: the note turns on a red warning and its button is disabled.
- A floating **allowance ring** at the bottom right fills from gray to purple, clockwise, as the $10 daily token allowance is used. When it is full, the board pauses and asks the person for permission to continue.

## Partner Review Problem 8

How each visual element is derived and what it is bound to.

| Element | Source | Rule |
|---|---|---|
| Tickets on the desk | `GET /api/tickets`, polled every 2 s | `state` = `resolved` only when `tickets.status = 'closed'`. A finished run on an open ticket shows "Run finished". |
| Start buttons | `team_working` / `GET /api/runs` | All disabled while any run is `running`, while the budget is paused, and for resolved tickets. The backend also returns 409. |
| Wall summary | events whose `run_id` belongs to the selected ticket | `run_id` to ticket comes from `GET /api/runs`, which lists only runs started since the backend last started, so a database reset shows a clean wall (finished runs since the last reset are rebuilt from the audit trail when the backend restarts, so a code reload doesn't make worked tickets look untouched). The Boss note, the request, and the timeline of events (the per-agent summary was removed as redundant with the timeline and the audit trail). |
| Boss note | `status` events | Latest `status` event, earlier ones under "Earlier updates"; falls back to the run result. |
| Robot mode | `activity.ts:deriveActivity` | See below. |
| Exchange line | `received` / `message` / `check_in` events younger than 3.5 s | Dashed violet line (task or answer) or blue (check-in), animated dot from sender to receiver. |
| Waiting arrow | open tasks with an open child task | Dotted amber arrow from a waiting agent to the agent it waits on; drawn only for agents whose mode is `waiting`. |
| Balance | `GET /api/balance` | A change between polls shows a `+/-` marker for 12 s. |
| Allowance ring | `GET /api/budget` | Arc = `spent / 10`, clockwise from 12 o'clock. At `paused` the modal opens; `POST /api/budget/reset` appends a `budget_reset` entry. |
| Approvals | `GET /api/approvals` | The control panel (heading, name field) sits below the balance at the far left of the desk. Pending notes form a stack next to it: one is shown in full and a chip per note brings any of them to the front, so they can be decided in any order (the selection stays put when a new note arrives); the 3 most recent decided notes pile at the far right and the `‹ ›` buttons above the pile click through them (they stay put however tall the note is). Kinds: payment, purchase, customer message (shows the exact reply text; approving records it on the ticket, nothing is sent). Pending items get Approve/Decline, which require a name (max 100 chars). A pending payment larger than the current checking balance shows a red warning and its Approve button is disabled ("Approval blocked"); Decline still works, and the block clears when cash covers it (`blocked` / `block_reason` from `GET /api/approvals`). Each note shows the agents' justification, concerns (database-generated warnings first, then the agents'), margin note, and what was checked: the agents' checks plus verified figures (cash before/after, other owed invoices and rent, cash if all were paid, open tickets). After a decision, the three most recent decided approvals (by `decided_at`, newest first) stay on the desk with the case collapsed; older ones drop off the desk but remain in `GET /api/approvals` and the audit trail. |
| Heartbeat | `GET /api/heartbeats` (live, from `team.HEARTBEATS`) | Every running agent shows a pulsing ♥ line on its name tag: what it is doing and for how long (`waiting for the model · 14s`, `using read_invoices · 3s`, `waiting for Facilities · 22s`). A model wait over 30 s adds `(slow reply)`; no tick for 6 s shows `no heartbeat for Ns` in red. It tells the user the agent is alive and what it waits on, so a long step is not mistaken for a glitch. It is not stored and does not prove the model will answer. It is display-only: no run, timeout or check-in depends on it, and if the endpoint fails only these lines disappear. |
| Price call | `DiscountAnalysis` in the Accounting reply; the customer note's approval | On a price-override ticket the team must name one unit price above the 30% margin floor and below list. Accounting returns it with reasoning, the Boss decides it, and the note to the customer (the approval a person reads) states it with the quantity total. A reply with no such price is refused by `write_messages`. |
| Plans vs. cash | `approvals` rows with `blocked` | Agents always prepare the payments and orders a ticket needs, even when cash can't cover them; the shortfall appears in the note's concerns. The only place a payment or order is stopped for cash is the approval step: the red warning, the disabled Approve button and the 409 from the approve route. |
| Check-in | `check_in` tool calls; `delegate` / `check_in` return values; `received`/`message` events | `delegate` waits 60 s; if the teammate is unfinished it returns a CHECK-IN report (elapsed time, time since last activity, recent steps including the teammate's own delegations; "probably stuck" at 60 s quiet). `check_in(to_agent)` waits another 60 s; `give_up=true`, or the 8th check-in, cancels the task. Every delegate/check_in result also ends with a STILL WAITING ON line naming the Boss's other pending teammates and how long each has been quiet. A teammate whose model call fails is retried once automatically before the caller is told. On the board: a blue exchange line from the checking agent to the checked one when a `check_in` event is under 3.5 s old; a working agent with no logged event for 45 s shows "quiet N s". |
| Boss update to the user | `status` audit entries from the Boss-only `status_update` tool | The Boss posts 1-2 plain-English sentences (no ids, JSON or tool names) at start, after each finding, when waiting on someone, when an approval is needed, and at the end. The wall shows the latest one as "From the Boss" with a spinner while the run is `running`; earlier ones sit under "Earlier updates". With no update yet: "Getting started…", then the run result. A blank update is refused and not logged. |
| Information hub | `delegate(known=...)` / `ALREADY GATHERED FOR THIS TICKET` in `received` events | The Boss passes the complete replies it holds (for example the lease rows from Facilities) to later teammates, so each fact is fetched once per ticket. `known` is capped at 8000 characters and refused for Customer Service. An identical `delegate` in one prompt returns the earlier reply and is not counted as a handoff. Paraphrased repeats are not caught; passing `known` is prompt-driven. |
| One ticket at a time | `POST /api/tickets/{id}/run`, `RUNS`, `team_working` | The backend refuses a run while any run is `running` (409, names the busy ticket). The board disables every other ticket's Start button and labels it "Team busy on #N". The button re-enables when the run's status leaves `running`. A pending approval does not block the next ticket. |

**Robot mode derivation** (per running run, events in order): a `received` event opens a task for that agent, with parent = the latest open task of the sender. A `message` or `error` event by an agent closes its latest open task. A task with an open child is `waiting`; a task without one is `working`; an agent with no open task is `idle`. A fresh handoff overrides the mode with `exchanging` for 3.5 s. Tasks are tracked per instance, not per agent name, so the same agent can be `working` on one task while another of its tasks is waiting. At least one agent is always `working` while a run has an open task. A `working` agent with no logged event for 45 s shows "quiet N s" on its tag.

**What cannot be fixed here (external to the design):**

- **Gateway stalls.** The model gateway intermittently stalls or returns 500 on a request. The agents have no control over it, and the stalls are not tied to an agent, prompt, output type or model setting (tested: default, `reasoning_effort=low`, `send_reasoning_ids=False`, `store=True`; each completed in 8 to 31 s, with the 31 s case being one stall retried once). A stall cannot be detected before the 30 s timeout, so a stalled attempt always costs at least 30 s, and a request that stalls on all 5 attempts costs about 150 s.
- **What the design does instead.** It bounds and exposes the damage: 30 s per attempt; one automatic re-run of the failed task; the caller told plainly after that; check-in reports and the `STILL WAITING ON` line so the Boss notices a quiet teammate; a "quiet N s" tag on the board; a stopped task logged as a note, not an error. It does not make a run faster or guarantee completion.
- **Parallelism is limited by the Boss.** The Boss is one model session. While a blocking `delegate` or `check_in` is open, it cannot act on another teammate, so a quiet teammate waits for the Boss's next step. Check-in cadence is therefore a minimum of one 60 s round, not a guaranteed interval.
- **Prompt rules are not guarantees.** One ticket per run, teammate selection and the payment review sequence depend on the model following its prompt. The code refuses only what it can check (see `output/harness.md`).
- **An in-flight run does not survive a restart.** A backend restart or code reload ends it, and the board then shows it as failed (finished runs since the last database reset are rebuilt from the audit trail, using `data/last_reset.txt`). The audit trail keeps what was logged.

**Constraints:** the board reaches the backend at `http://localhost:8000` and Vite is pinned to port 5173 (`strictPort`) because the backend allows only that origin; open it as `localhost`, not `127.0.0.1`. `prefers-reduced-motion` disables the animations; the hop is reset by a timer, not `animationend`.

## Partner Review Problem 9

What changed in the board while running the tickets to the end. Every change here is about looks or ease of use; the rules behind them are in `output/harness.md` and the READMEs.

| Change | Why |
|---|---|
| One "Needs your approval" section with one name field, at the far left under the balance. A second copy of the section that appeared by mistake was removed. | A person signs in one place; two name fields invited confusion. |
| Pending notes became a stack. One note shows in full; a chip per note (with a count) brings any of them to the front; a new note joins without moving the one being read. | The earlier row of notes clipped the third one off the screen and forced one approval before the next appeared. Approvals should be decidable in any order. |
| Decided notes pile at the far right, three most recent, with `‹ ›` buttons in the "Decided" heading row, aligned to the pile's right edge, and a white heading. | The buttons used to sit under the pile and jump with the height of each note. |
| A payment or order larger than the checking balance shows a red warning, a ⚠ on its chip and a disabled "Approval blocked" button. Decline still works. | The person sees why it can't be approved instead of discovering it by clicking. |
| Customer replies appear as a third kind of note (Customer message) showing the exact text, why it is the right reply, and what was checked; on a price override the text states the decided unit price and total. | A person reads the real words, and the price, before anything counts. |
| The "What each agent did" summary was removed from the wall. | It repeated the timeline and the audit trail. |
| Each name tag gained a heartbeat line (`waiting for the model · 14s`, `(slow reply)` after 30 s, red `no heartbeat` if it stops). | During long waits it should be clear the agent is working, not glitching. |
| More space between the name tags and the ticket heading on the wall; the balance card's top lines up with the top of the ticket papers. | The tags (taller with the heartbeat) crowded the heading; the balance floated higher than the papers beside it. |
| Tickets whose run finished keep their "Run finished" badge after a backend restart (finished runs since the last reset are rebuilt from the audit trail). | A code reload used to make worked tickets look untouched. |
| Because agents now always prepare the payments and orders a ticket needs, more notes appear on the desk (for example a restock order on a price-override ticket). | The person decides, instead of the agents deciding silently not to ask. |

