# AI Prompts

## Problem 1: Vibe Coder Prompts

1. We are working in the HW5 folder today.
2. create an AI_Prompts.md
3. Place 10 "Problem X" headings in the file. This will be used the same way as it was in the other HW projects, all the user propmts will be placed there, the user will tell you when to progress from one to the next.
4. Create a Problem 11 as well
5. Update the problem headings to: 

   ~~~text
   Problem 1: Vibe Coder Prompts
   Problem 2: Study the Campus Customs database
   Problem 3: Build the MCP server
   Problem 4: Add the MCP server to vibe coder and test each tool
   Problem 5: Build the agent team and grow the MCP tools
   Problem 6: Plan the three tickets
   Problem 7: Backend Routes
   Problem 8: Agent Dashboard
   Problem 9: Resolve the Tickets
   Problem 10: Reflection
   Problem 11: Submit to Github
   ~~~

## Problem 2: Study the Campus Customs database

1. Moving on to Problem 2, create a 'data' folder
2. Create an 'outputs' folder and create a 'harness.md' in the folder.
3. Change the name to 'output'
4. Create a requirements.txt in the HW5 folder, a .gitignore, a .env (copy this from HW4), and README.md. The requirements and readme can be empty for now, we will update them later
5. copy the whole root .env and the .env.example. I want the API key to be in the .env. Make sure the .env specifies GPT-6-Luna
6. I've added two databases to the data folder. the  'new' database will be updated by agents, and the other should ever be updated. Should I record this rule in the harness.md?
7. Write it into the harness.md but do not make the chmod read only change yet
8. Look at the database, there should be three 'open tickets' please sumarize them
9. How can i open this database?
10. Use python, run it
11. In the harness record the following: Required Rules of the shop:

    ~~~text
    - "today" is whatever `desk.date_today` says, not the real date. Use that to figure out what's overdue.
    - Vendor lead times live in the `vendors` table, so check there and never guess.
    - Vendors won't ship anything new if we still have an unpaid invoice with them. Pay that off first (or flag it) before trying to restock.
    - Any payment needs a human to approve it first. No exceptions, we lose points if this gets skipped. And once a payment actually goes through, update the right tables so the db matches reality.
    - If there isn't enough cash, the pay tool should just refuse. Cash can never go negative.
    - Money only goes OUT in this hw. We didn't model revenue, so nothing ever comes in.
    - Before doing a full run on the tickets, reset the db back to the original values so we're starting clean.
    - Do NOT contact real customers or real vendors. Just write drafts and leave them on the board.
    ~~~

12. In the Harness include the following explanation of the db fields:

    ~~~text
    tickets - These are open tasks and will be closed, maybe written.
    inventory - product stock by size
    pricing - Unit cost and list price per SKU
    vendors - These are the suppliers: Bulldog Print Co, Elm City Gifts, QuickShip CT
    invoices - Self explanatory, these may be updated
    leases - Chapel Street shop, $2,400/mo
    cash_accounts - Checking, $3,400, this will be updated throughout the HW
    payments - Empty, so no payments have been made yet, but may be
    desk - Today’s date, 2026-08-31 (this is not the actual date but is the assumed date for the sake of the assignment)
    ~~~

## Problem 3: Build the MCP server

1. Moving on to problem 3. Do you have access to FastMCP?
2. Ok, move forward with that venv and requirements build. Make a mcp_server folder. The serve will talk to the 'new' db
3. What are the fields in each of the db tables?
4. Create the following tools in the MCP Server for the agents to call, and add the bulleted descriptions to the harness:

   ~~~text
   1. read_inventory
      * Which table it reads: inventory, and returns all the values including sku + size (together the key), name, qty, location
      * Particularly helpful for: Inventory agent.
      * Which Ticket it helps with: 101
      * Why this matters for the ticket: Addressing ticket 101 requires information of whether there are currently shirts in stock to meet the customer need, therefore the inventory level needs to be communicated to the inventory agent, boss agent, and all others to coordinate actions.
   2. read_invoices
      * Which tables it reads: Invoices,  and returns id (key), vendor_id, amount, due_date, status, description
      * Particularly helpful for: Boss agent, Inventory agent, Accounting Agent
      * Which Ticket it helps with: 101, 103
      * Why this matters for the ticket: Tickets 101 and 103 both require an agent to understand whether there is an action in process (in the case of tickets 101 and 103 a decision to purchase new inventory) in order to effectively share information with customer service about lead time or with accounting about ordering more inventory.
   3. read_balance
      * Which table it reads: cash_accounts 
      * Particularly helpful for: Accounting agent
      * Which Ticket it helps with: 101, 102, or 103
      * Why this matters for the ticket: For any cash outflows (such as in any ticket - 101, 102, or 103) the payment should only be made when there is adequate balance remaining in the company checking account, this allows the accounting agent to provide that information before the Boss or a human makes any decisions.
   ~~~

5. In the MCP server file add a specific ReadMe.md that describes the use of the MCP server, the db file it uses, and the tools that were just made.

## Problem 4: Add the MCP server to vibe coder and test each tool

1. Moving on to Problem 4, confirm whether the MCP serve is saved to this project so that the tools can be called
2. Yes, connect it and create the HW5/.mcp.json
3. create an output folder and an empty mcp_smoke.json
4. Load the MCP server.
5. Re-read the conversation and make sure that my prompts are added to "AI_prompts.md" verbatim
6. Confirm now whether you are connected to the server. Another session confirmed that was the case
7. Use each tool individually and place the output results into mcp_smoke.json. For each include this prompt, the tool name, and the tool output in three different lines.
8. Show me the inventory table

## Problem 5: Build the agent team and grow the MCP tools

1. Moving on to Problem 5 in HW5, we are going to build an agentic team comprised of the following agents: Boss, Inventory, Accounting, Facilities, and Customer Service. The architecture must be that any of the agents can communicate to the others and can delegate activities to the others. These will be made using PydanticAI. Create individual prompts files (currently shells), the models used should ALWAYS be gpt-6-luna. The prompts for these will be in a prompts folder inside a backend folder (make that). Agent files are directly in backend. Complete this then ask me clarifying questions about what data types need to be included in a backend/models.py folder --- the other HW folders may have examples.
2. Add this tool as well:

   ~~~text
   read_ticket

   * Which table it reads: tickets, and returns all fields 
   * Particularly helpful for: boss
   * Which Ticket it helps with: any and all
   * Why this matters for the ticket: In order for the boss to delegate effectively it must review the needs of the store at any one time, plan, then delegate to the agents.
   ~~~
3. I will answer the models.py questions later.
Add this tool as well: 

   ~~~text
   1. write_ticket
      * Which table it reads: tickets, and can update the status and notes fields
      * Particularly helpful for: boss
      * Which Ticket it helps with: any and all
      * Why this matters for the ticket: In order for the boss to close a ticket it must be able to update the database and change the status to ‘closed’ so that it does not continue to delegate once agents have completed all delegated actions. The ‘notes’ field should be updated with the date closed, the actions taken to close the ticket (including suppliers worked with and the delegation framework), and any exceptions that had to be handled by a human user.
   ~~~
4. Also add:

   ~~~text
   1. read_lease
      * Which table it reads: lease, and returns all variables
      * Particularly helpful for: Facilities Agent
      * Which Ticket it helps with: 102, and future rent payments
      * Why this matters for the ticket: This may be required to check information regarding the lease payment ticket creation
   ~~~

   I will answer the other questions later.
5. Create a write_inventory tool as well, suggest the best structure. Use my template.
6. create read_vendor, read_pricing, read_invoices, and write_invoices tools in the same template
7. What field would record the lead time of an expected order?
8. create tools for read_cash_accounts, write_cash_accounts, and read/write_payments.
9. I want you to make prompts for each of the agent teammates. My drafts are below. Please review these and add best-practice details so they are more robust. Keep a lot of my writing but just add the critical details I'm missing. Consider what data types will be passed between these agents to perform their roles well and create those structures in models.py. 

   ~~~text
   Boss (Boss.md): 
   Core responsibility: You are the executive of a team of agents. Your core responsibility is to review open tickets in the campus_customs_new.db and delegate actions to the various teammates to close those tickets.
   how frequently work streams or data is checked for: see below
   where the data comes from: tickets in campus_customs_new.db
   Which tools will you use: read_ticket, Write_ticket.
   which agents they can collaborate with and for what: Your agent team is “Inventory,” “Accounting,” “Facilities,” and “Customer Service.” These agents may also delegate ticket writing and management to you. Inventory may request that a new order is made to top-up the in-store supply of a good. Accounting may prepare a payment request, provide the cost and expected margin (making sure that it is suitable), create a payment hold given the account balances, or prepare payments for human approval - this is not exhaustive. Facilities may request that you create a ticket to have a human approve a rent payment. Customer service may work with other agents or you to create meaningful updates to customers with tickets outstanding. Only use db facing tools to review the tickets table, otherwise ask the responsible agents. 
   where orders come from: The agent teammates may request that you track something as a ticket, or the user may generate a new request. In either case you need to delegate these tasks and track them as tickets until they are closed.
   How many communication loops are permitted in response to one prompt: 20
   What this agent can do: Read and write tickets, delegate to others.
   What this agent cannot do: Read or write to the db outside of the tickets table.
   Other instructions: These agent actions may take several business days to close, so you should check on the work streams three times per business day (8am, Noon, 4pm) and whenever a human prompts you to. For example, vendors may take time to make and delivery product after an order. There are situations where you must make final calls after information is received from the agents, on a bulk order discount offer, for example. In a case such as this there should always be at least a 30% profit margin retained and accountant suggestions should be checked against that
   data types will be in models.py



   Inventory (inventory.md): 
   Core responsibility: You own the responsibility of ensuring inventory adequacy in our clothing store, including requesting new orders when stocks are low.
   how frequently work streams or data is checked for: 
   where the data comes from: see tools. 
   Which tools will you use: read_inventory, write_inventory, read_vendor, read_invoices.
   which agents they can collaborate with and for what: You work on a team of agents - the Boss (delegator), accounting (bill paying and review), facilities, and customer service. You will answer to boss and customer service, and may receive questions from accounting. this is non-exhaustive. Work will be delegated to you by the boss agent from open tickets. You can request tickets be made and progressed by the boss agent. If you have any questions about open tickets, orders, or invoices you can ask the agent team. 
   where orders come from: The Boss agent, there may be communications back and forth with the Accounting and Customer Services agents as well.
   How many communication loops are permitted in response to one prompt: 20
   What this agent can do: write to inventory, read elsewhere as provided by tools, and chat with other agents.
   What this agent cannot do: write to database tables other than inventory.
   Other instructions: ‘Low stocks’ or ‘low inventory’ is nuanced, take into account lead times and minimum order quantities. 
   data types will be in models.py



   Accounting Agent (accounting.md): 
   Core responsibility: You own the responsibility of accounting in a clothing store. This includes making sure that payments are not made if there are insufficient funds in the checking account, and any offered discounts or prices do not dip below a 30% margin. You will also prepare tickets for various charges at the store by request of other agents or the user. The agents will ask for the information that they need. 
   how frequently work streams or data is checked for: Upon external request.
   where the data comes from: 
   Which tools will you use: All read tools are available to the accounting agent aside from read_ticket and read_lease. The only write tool available to the accounting agent is write_invoices, write_cash_accounts, and write_payments.
   which agents they can collaborate with and for what: Customer service, inventory, boss, and facilities, the whole team. 
   where orders come from: Facilities, Boss, Inventory, and Customer Service (they may ask for lead times)
   How many communication loops are permitted in response to one prompt: 20
   What this agent can do: A lot.
   What this agent must not do: Never share information about pricing (other than list_price), vendors (other than lead_days), invoices, leases, cash_accounts, or payments with customers.
   Other instructions: Never approve payments to be made, the human user’s approval is required for this.
   data types will be in models.py 

   Facilities Agent (facilities.md): 
   Core responsibility: Request a lease, utilities, or other facilities payments ticket be created by the accounting agent and tracked by the boss agent.
   how frequently work streams or data is checked for: Weekly, at the beginning of the week.
   where the data comes from: the leases table in the campus_customs_new.db
   Which tools will you use: read_leases 
   which agents they can collaborate with and for what: Boss Agent and Accounting Agent
   where orders come from: You create the orders, there may be follow up questions from the boss agent or accounting agent.
   How many communication loops are permitted in response to one prompt: 20
   What this agent can do: share information from the leases table of the db
   What this agent cannot do: Do not share information regarding leases with the Customer Service Agent. 
   Other instructions: A lease payment ticket should be made 20 days from the due date. 
   data types will be in models.py

   Customer Service (customer_service.md): 
   Core responsibility: Your role is to answer customer questions about the inventory availability, pricing, and lead time for new inventory to be delivered. You are the front door to the company but are working with sensitive information and must be very careful about what is shared. Never share information about pricing (other than list_price), vendors (other than lead_days), invoices, leases, cash_accounts, or payments with customers. 
   how frequently work streams or data is checked for: Whenever a customer request comes in, or when the boss agent asks for an update.
   where the data comes from: Agent teammates. 
   Which tools will you use: Do not directly use db facing tools, instead ask the agent team for information directly. 
   which agents they can collaborate with and for what: Inventory will provide the inventory details, boss can provide the status of tickets and orders. There are not any reasons to chat with the other agents, but you have the ability to.  
   where orders come from: Boss and Customer chat window. 
   How many communication loops are permitted in response to one prompt: 20
   What this agent can do: 
   What this agent cannot do: See above.
   Other instructions: Respond to customers in a very polite but direct manner, do not be wordy.
   data types will be in models.py
   ~~~
10. Make the following changes:

    ~~~text
    * create audit_trail.json in the outputs folder
    * Make sure that for every loop-step of every agent it is adding the time, the tools used, the data or message returned, and to whom or what. 
    * Make sure the audit_trail.json is never wiped, only appended.
    * Add the agent tool permissions from their prompt into harness.md. 
    * Add a max $10 of tokens per day use to the harness.
    * Add a safety section into harness.md - describe the guardrails that I’ve designed for the agents (specifically the accounting-boss checking, the human payment approval, the customer service information limitations, and the daily token cost limit)
    * Although it is inefficient, I want you to put all the redundant team/shop shared_rules.md and team.py information into each of the agent prompts and to delete these files. 
    * update mcp_serve/README.md so the tool list matches the current reality. 

    Confirm the following:

    * The data types in models.py are clear, there are no outstanding issues or questions, and they are efficient given the data handling expectations.
    ~~~
11. Responses to open questions and tasks:

    ~~~text
    * No shop-date tool: Your rules say “today” is `desk.date_today`, but no tool reads the `desk` table. Agents are told to use the date given in their task, so something has to supply it. I’d add a `read_desk` tool or pass the date in with each run.
    * Do this an give the ability to check to all agents.
    * No scheduler: The Boss’s 8am, noon and 4pm checks and Facilities’ weekly check need something outside the agents to start them.
    * How can this be accomodated.
    * Drafts have no home: “The board” for customer drafts is still undefined.
    * Write a process for the customer service agent and boss agent to draft customer service messages in a private chat between them before sending. The boss should check that the message does not contain sensitive information. 
    * Clarify if you are refering to payments instead.
    * 20-handoff limit: I enforced it in `team.py`, along with the existing 4-level nesting limit. A Boss–Inventory ping-pong test stopped after 4 handoffs.
    * Margin definition: I assumed (price − cost) ÷ price. Please confirm that isn’t markup on cost.
    * Confirmed
    * Payment kinds: Only invoice and rent are supported, because utilities aren’t in the database.
    * Ok drop any mention of utilities in prompts.
    * Stock counts: `CustomerFacingInfo` lets Customer Service quote exact quantities. Say if you want a yes/no only. 
    * Provide more than or less than 5 to customers.
    * Ticket `type` values are free text.
    * No tools wired in: The agents still have only `delegate`. The prompts name tools like `read_inventory`, but the agents can’t call them until we connect them. That is the next step.
    * Ok do this now.
    ~~~
12. 
    ~~~text
    confirm (answer Y/N, and an explanation if N)
    all agents use gpt-6-luna
    all agents have my portly api key
    the data types are advisable and not prone to errors
    The agents all have the ability to speak to one another
    The tools are wired
    the agents record to the audit log
    The agents are aware of the harness safety rules (if not add these to the prompts)
    ~~~

    I respond to the rest of your points in the next message

13. 
    ~~~text
    Here are my clarifications:

    * Payments vs. drafts: I meant drafts of messages to people, such as customer replies. I did not mean payments. Payments have no drafts, because write_payments makes a human approve each one. One gap remains: your rule also covers messages to vendors, such as a reorder email to Bulldog Print Co, and those have no review step yet. Should vendor messages go through the same Boss check?
       * Yes, and describe this in the harness
    * Scheduler: Something outside the agents has to start the Boss checks at 8am, noon and 4pm, and the weekly Facilities check. I’d put a small scheduler inside the Problem 7 backend. It would call run_team("Boss", ...) at those times and Facilities on Monday mornings. It would share one process with the approval handler and the budget cap. The dashboard would also get a “check now” button for human prompts. At gpt-6-luna prices, a day of checks costs a small fraction of the $10 cap. OS cron or a Claude scheduled task would also work, but they can’t show approval prompts. Want me to build it?
       * I don’t want to do this if committing this project to a repo would break the build. I will have this graded afterwards and if there is a chance of breaking then we should simply drop that functionality.
    * Stock band at exactly 5: You said “more than or less than 5”, so I made 1 to 5 read “5 or fewer” and 6 or more read “more than 5”. Tell me if exactly 5 should read differently.
       * The approach you took was perfect >5, <5, 0.
    * Ticket types: 
       * all data pulled from the database or with likelihood of being deposited in it should be sent between agents as validated data types. Some of these will remain strings.
    * 20-handoff limit: Your reply to that item had no instruction, so I changed nothing. The 20-handoff cap and the 4-level nesting cap stay as they are.
       * Perfect


    Still open

    * Approval handler: Nothing registers one yet, so every payment is declined until you or the dashboard does. That is the safe default.
    ~~~
14. Create a boss review loop for any proposed payments in the context of other open tickets (for example, it checks if all the open tickets were paid where that would leave the cash_balance. It can ge tthat information from the accountant. Add that to it's prompt

## Problem 6: Plan the three tickets

1. 
   ~~~text
   Moving onto Problem 6, I want to create an html file under the output folder that can be opened locally and contains one page each for each of the currently open tickets, a Cash page, and a Reflections page.

   Ticket 101
   First Boss Call: Inventory
   All the expected agent delegations: Inventory reads inventory, confirms to boss that there is a CC-TEE-WHITE in S available, Boss or Inventory tells Customer Service, and Customer Service and Boss draft a message for the customer telling them it’s available.
   Which MCP tools are expected to be called: read_inventory and read_ticket

   Ticket 102
   First Boss Call: Accounting
   All the expected agent delegations: Boss checks with accounting that there is enough money available, accounting checks accuracy with facilities, accounting returns to boss that it is accurate and that there is enough money to pay this, Boss checks whether this can be pain in addition to other open tickets and messages user.
   Which MCP tools are expected to be called: read_leases, read_cash_balances, read_desk, read_ticket

   Ticket 103
   First Boss Call: Inventory
   All the expected agent delegations: Inventory and Accounting - how many do we need to order, how long is the lead time, who will we order from, what is the price, what is the minimum price to make our 30% margin.
   Which MCP tools are expected to be called: read_inventory, read_vendor, read_cash_accounts, read_invoices, read_desk, read_pricing, read_ticket

   Cash - “coming later” 

   Reflection - “coming later”

   On each of these tabs my input above will be under an “Expected” section, and after the test run the results will be placed in an “Actual” section. Create both of these sections but leave it empty for Actual.
   ~~~
2. 
   ~~~text
   Correct the tool name spelling errors.
   Also since there are no tees then change the expectation for 101 to the following:

   Ticket 101
   First Boss Call: Inventory
   All the expected agent delegations: Inventory reads inventory, confirms to boss that there is a CC-TEE-WHITE in S available, Boss or Inventory tells Customer Service, and Customer Service and Boss draft a message for the customer telling them it’s not available, this will trigger a call to the vendor look up to determine whether there is time remaining on the lead time versus the desk. 
   Which MCP tools are expected to be called: read_inventory, read_vendor, read_ticket, read_desk

   And add the boss payment review and human approval step
   ~~~
3. Availabel was a slip, please update ticket 101's expected text.

## Problem 7: Backend Routes

1. Moving onto problem seven, we need to create a backend. Use fast API to add the following routes to the main.py file. First, we need to handle the return of the three tickets that are open and whether each one is open or resolved at any given point. We also need to take a ticket ID and run the agent team on the ticket. We also need the backend to be able to return recent agent events, specifically what each agent was doing, what they said, which tools they used, so the board can refresh. The backend also needs to return the current checking balance from the cash underscore accounts table in the database. When I want to try a fresh run, I want to reset the database to the original values. This is not something that happens every time, it's just a function that can be used. The backend also needs to handle a route for approving a payment or purchase after a human clicks approve. Specifically, agents only prepare the pay and the route. Is what actually changes cash. Ask me any questions if any of that is unclear.
2. First, clarify what CORS is
3. The server needs to be able to start with the following command: uvicorn main:app --reload --port 8000. Confirm that's the case and then start with the back end. From the routes that I described, create brief one-line descriptions in output forward slash harness.md. That line should cover what the URL is and what it does.
4. I increased your effort level, test this problem 7 build for bugs once more.
5. Does this build run against anything i did in problem 5 or 6
6. Update the ticket 102 expectation by aligning it, very succintly and naturally, to the new flow.

## Problem 8: Agent Dashboard

1. We're moving on to problem eight, and we're going to build an agent dashboard front-end module that allows me to track agent interactions. You're going to do this under the front-end folder, and it will be built using React, Vite, and TypeScript. I want the board to include the checking balance. For example, it should drop after a payment is approved. It should let a human approver pay or purchase, or rather, approve a pay or purchase request when asked. It should show a short summary of what each agent did on any given ticket. I also wanted to have a visual representation that a ticket is resolved when a run to resolve that ticket is finished. It should let the human user pick a ticket and start the agent team working on it. This way, we don't need any automated running. It's completely driven by the human picking the ticket to work on at a given time. And all three tickets should be listed for the human user to view.
2. Stylistically, I want this UI to look like a cubicle where the tickets that are open are in front of you. And on the wall of the cubicle, when you select the tickets, there are summaries. Like the ones, or rather including the ones that are requested in my last message. The agents should be represented as robots that are peeking their head over the top of the cubicle. The look of the animation should be clean and minimal, not cartoonish. when the user Scrolls their Cursor Past one of the animated agent representations. They should react or jump in some consistent way. They should also have name tags And while they are working, there should be some representation visually that they are exchanging information between one another, working on their own, or idle. There should also be a representation of when they have hit their $10 limit. Something like a floating circle on the bottom right-hand side of the program. That goes from gray and gradually fills with purple clockwise and completes three hundred sixty degrees of the circle once ten dollars have been spent. Once ten dollars have been spent, the dashboard pauses and asks the human for permission to continue. To reset the allowance.
3. front end. Make sure that the front end can reach the back end at the localhost port 8000 URL. Regarding the back end, allow the vite page origin of the localhost port 5173. So the browser is allowed to call these routes. Make sure the board starts with the terminal command npm run dev. This must open the React desk in my browser so I can pick tickets and watch the agents. Run it so I can test it.
4. [An image was attached: a photo of an interior with floor-to-ceiling windows and dark mullions looking out at a city skyline with the Seattle Space Needle, with grey half-walls in the foreground.]

   ~~~text
   STEP 1: Make the UI have feel like this photo, create a wood desk with the tickets and the summaries on the grey back splash and a window into a city scape (I'd prefer NYC skyline) at the top of the page. 
   STEP 2: The Robots should be more differentiated.
   STEP 3: There were instances when I tested this that all the robots showed they were waiting on another, but this was not accurate. This is unclear to the user.
   STEP 4: The Inventory bot got stuck while responding to ticket 101. Create a loop so that boss or other agents can check in
   ~~~
5. Provide a link so I can start and check this new build
6. The interface was far better, but the agents asked for rent to be paid (ticket 102) when ticket 101 was being worked on. additionally, the agents timed out. I think that the ticket should be worked on, approval requested then the agents should stop working on the ticket (without an error occuring). Also the facilities agent was contacted. tighten up the prompts so that only focused conversations are had

   Lastly, write 

   ~~~text
   design.md, and the output folder. Summarizing the following thoughts. about what I chose for the dashboard book. First, going off the desk theme, I decided to build this around the idea of having tickets for to-dos physically on your desk. And then once they were delegated, to the agent team the information would begin to accrue like a desktop but without a desktop rather just on the backsplash of a desk when I did one iteration of this the output was relatively boring and bland so I added some more background imagery to make it interesting to look at. Something that Yale SOM students would find interesting, like the skyline of New York City. I had the agents pop out of the top of the backsplash and have some interactive visual features. to show that work was going on. And which agent was doing what work at what time. Without this, it was really unclear if any work was being done at all. And how it was being done. output. Write design.md in the output folder. Summarizing the following thoughts about what I chose for the dashboard book. First, going off the desk theme, I decided to build this around the idea of having tickets or to do's physically on your desk. And then once they were delegated, to the agent team, the information would begin to accrue like a desktop, but without a desktop, rather just on the backsplash of a desk. When I did one iteration of this, the output was relatively boring and bland. So I added some more background imagery to make it interesting to look at something that Yale SO students would find interesting like the skyline of New York City. I had the agents pop out of the top of the backsplash and have some interactive visual features to show that work was going on. And which agent was doing what work at what time. Without this, it was really unclear if any work was being done at all. And how it was being done.
   ~~~

    Include the details from this prompt as well.
7. The agents should have their own individual access to a model session, make sure that's the case.
8. I want this to complete soon so I can move on, please stop working after making these current resilience improvements. I want to manually test the system again.
9. Finish this last change "Since I can’t fix the gateway itself, I’ll make the system resilient by retrying stalled attempts faster, having timed-out components return a message instead of crashing, and lightening the heavy OutlookRequest payload." then confirm that the agents are free to run on the next ticket after making the approval request, then reset for me to test. Do this efficiently
10. I should only be able to click on one ticket at a time. And the Boss should provide a status message to the user about what's going on in plain english
11. The context is getting pretty full. Before we run out of it, please review all the edits that have been made to the system design and agent interconnections. Update the README documents, the harness.md, design.md, and agent prompts for clarity about the actual design at this point. I want your additions to be added as "Partner Review Problem 8" and the text to be very technically precise, lacking in fluff, and succint.
12. Make sure the boss agent, in its prompt has a list of what agents have access to which tools.
13. Also add the check_in feature, the boss-user update feature, and the one-ticket-at-a-time feature to the design.md in the saem format as the other entries
14. The boss is not checking in with accounting in the most recent run, also facilityies and accounting appears to be prone to timing out. look into this.
15. Put this warning information in the readme and an explanation of what cannot be fixed in the design.md
16. Change the code so that approvals include rich detail from the team about the justification for paying the bill, what was checked, and if there are any margin or cash balance concerns given shop rules and the tickets.
17. Also ensure that the last three approvals stay visible on the desk after approval.
18. Make sure theses changes are covered in the appropriate project files under the same marker as I shared earlier in this problem. Then Compact the context for this session

## Problem 9: Resolve the Tickets

1. Moving on to problem 9. Clear the campus_customs_new.db so it matches the reference and start re-start it so i can test the build
2. I am noticing that sub-agents are asking the same questions to one another multiple times. I want the boss to be an information aggregator and disseminator, this way tools calls for the same information are only hapening once in a given ticket. The boss can do this by proactively passing the complete information gathered from agents to other agents when it is asking a follow up task (for example: lease information gathered from facilities to Accounting, so accounting doesnt again go to facilities unecessarily).
3. Also create an approval process for customer service messages that uses the payment approval tools.
4. Go ahead an kill the current run. Last change: Move the "needs your approval section below the cash balance on the desk, and the ticket shouldn't stack vertically, they should spread horizontally to the left from the approval section, once they are approved they should stack on the right side and be able to be clicked through.
5. Edits to the Last change: Move the "needs your approval" section below the cash balance on the far left of the desk, and the ticket shouldn't stack vertically, they should spread horizontally to the RIGHT from the approval section, once they are approved they should stack on the FAR RIGHT side and be able to be clicked through.
6. Reset the database so I can test THESE ticketS
7. restart again
8. The run finished successfully! go to the records on the database and the json and fill the fields on the actual portion of the page for each ticket. What tools did they use, which agents worked on the problem, and how delegations worked (from who to whom and when with what)
9. Keep the expected sections as-is
10. Open the html
11. Update the pay approval tool so that it stops the user from approving any tickets that would take the cash balance into the negative. The tickets can still be prepared, but the approval should be halted (button not functional) and a warning message appears. If you can reverse the approval of ticket 101 in the current session that would be helpful to demonstrate it worked.
12. reverse the approval again, but update the code so that the ticket is not visually going to allow the approval to move into the decided pile
13. reset the data based and restart the server. I want to run this again with this new edit complete. Also remove the 'what each agent did' area because it is redundant given the timeline and audit log.
14. Also make sure that that the accountant and other agents have a heartbeat function similar to the boss, this makes sure that during long work periods it is clear to the user that they are not glitching.
15. Then reset the project and provide a new link
16. Scratch that, make the yellow tickets awaiting approval stackable as well. Last run there were three and I could only approve the first two that were made. In reality I would want to approve these requests in whatever order I wish and I had to approve one before the final one showed during the last run.
17. Make sure that the heartbeat implementation is not going to introduce a stricter operating constraint than is already proven by the boss, I do not want to add a new failure mode due to waiting.
18. Once this is complete re-run the program so I can test, I do not need your test
19. There are two 'needs your approval' sections for signature input. I only need one. Make this change
20. The tickets ran but the agent team did not generate a payment to-be approved by the user. I still want these payment plans to be generated, but I want the handling of the non-payment of things that would provide negative balances to occur in the signature and approval part of the program, not the generation by the agents, make that clear
21. And make the necessary change. I will re-run the agent team on Ticket 103 as a test
22. Put the buttons that allow you to shuffle the decided stack to the top so it doesn't jump around based on the height of the current ticket.
23. Move it to be in-line with the Decided heading, to it's right and aligned with the right edge of the approved plans. Also add padding between the agent status boxes and the headings below
24. Make the decided heading text white
25. Move the cash balance reader down so that the top is aligned horizontally with the top of the white ticket start buttons
26. The payment was still able to be approved by the user. This isn't working. How do you suggest handling the shop rule "If there is not enough cash, the pay tool must refuse - no negative balances" in this case given the build?
27. Check the db for the actual MOQ from the hoody supplier - I am concerned that it is not actually possible to order the exact amount the agents suggested
28. Carry this out, then reset the db and the front end and we will finish the run and the project:

What I suggest: apply the same gate to purchases. I would block approving a purchase when its amount exceeds the current checking balance, using the same warning, disabled button and 409 refusal as payments.

* Agents keep preparing plans: the plan is still generated, as you asked. Only the signature step is blocked.
* Single place for the rule: the “no negative balances” rule stays in `approvals.decide` and the board, not in agent judgment.
* Accurate warning: the approval note already shows the shortfall, so the red warning would say why.
* The 103 restock can’t be approved here: with $160 and no inflows, the $264 order would stay blocked. I think that is the honest outcome, and your options would be to decline it or to approve it only after cash is available.
29. it seems like the accounting model is timing out, why is that?
30. move the declined t-shirt payment back to unapproved
31. Clear the db and the audit log for anything associated with ticket #103 from the recent run starting 9:52 PM, I want to run this again and have the agent team suggest a price that outperforms the minimum margin target. They have the freedom to use their judgement within that rule. I want them to be forced to make a call. Write this into the prompt of the accountant and make sure they record this int he note to the AI club.
32. I will manually re-run, just clear the information that I requested
33. including the ticket status
34. I meant reset the ticket status only for 103, i want 102 and 101 to be completed or closed, whatever the status was moments ago.
35. just clear the whole db so we can restart the test once more
36. Just RESET the db so I can run the test once more
37. 1. The run finished successfully! go to the records on the database and the json and fill the fields on the actual portion of the page for each ticket. What tools did they use, which agents worked on the problem, and how delegations worked (from who to whom and when with what)
2. Keep the expected sections as-is
3. itemize the money out with the starting checking balance, how cash then changed with every ticket approved, include a clear discussion of why the purchase was approved and did not deduct from the cash balance because this was not an invoice, only a purchase order - so no cash is changing hands, and the ending checking balance
38. in output/resolved_tickets.json, for each ticket save: id, final status, short outcome, what each agent contributed, and any human approvals (date, time, who)
in output/resolved_board.json save a page that can be double clicked with a screenshot of the react board for each resolved ticket (101, 102, and 103)
39. First, Confirm that this run appended to the audit trail.json and it is the only one there.
Update Design.md with the changes that were made during this problem, they are  all aethetic or improving th euser expereince
Last, Re-review the harness.md and the READMEs so all the changes that were made are accurately reflected. The harness needs to cover tables, MCP server tools, five agents and their rules, API routes, the dashboard, and safety rules.
40. where is desk_tickets.html?
41. renamed ticket_report.html as desk_tickets.html

## Problem 10: Reflection

1. Moving on to problem 10, put the answers to the following questions in the Reflections tab of the desk_tickets.html

How would you evaluate the performance of the agents on each ticket and why?  
I thought the performance was best on ticket 102. And equally as bad on tickets 101 and 103. On the first, the objective was relatively straightforward and the pings between agents were minimal. For 101 and 103, there were some redundant pings going on and the accounting model seemed to time out relatively frequently. There was some interesting activity where the tickets were initially asking for approval of a combined payment and message, but in the later stages of refinement, the customer messages and payments or purchases were separately. Seeking approval, although this was not explicitly requested.

For each ticket, how did Actual compare to the Expected plan you wrote earlier?   
What would have been simpler as one agent with tools — and why?   
Describe three new problems Campus Customs might face that this agent team could solve with the tools you built   
Describe three new problems Campus Customs might face that this agent team could not solve with the tools you built, and explain the tools and agents you would need to solve them of the desk tickets HTML file. I thought the performance was best. I thought the performance.
2. Moving on to problem 10, put the answers to the following questions in the Reflections tab of the desk_tickets.html

How would you evaluate the performance of the agents on each ticket and why?  
I thought the performance was best on ticket 102. And equally as bad on tickets 101 and 103. On the first, the objective was relatively straightforward and the pings between agents were minimal. For 101 and 103, there were some redundant pings going on and the accounting model seemed to time out relatively frequently. There was some interesting activity where the tickets were initially asking for approval of a combined payment and message, but in the later stages of refinement, the customer messages and payments or purchases were separately. Seeking approval, although this was not explicitly requested.

For each ticket, how did Actual compare to the Expected plan you wrote earlier?   
I was right about the initial agent calls, but wrong about the complexity and the amount of back and forth it took. Before I finalized the design, I actually added a step where the boss shared all of its notes with agents that it had collected over time for a given ticket. This reduced the amount of excessive, redundant, or repeated tool use by individual agents to try and fact find for things that had already been called on previously. Once this was fixed, the behavior was relatively expected.

What would have been simpler as one agent with tools — and why?   
I think the facilities accounting and inventory agents could have all been collapsed into one general database management agent. That had access to all the tools. For calling and writing on the database. The accounting function of writing and the customer service function of writing I thought were appropriate as separate functions. And I really liked the fact that the boss had a robust review back and forth with each of these agents for calling and writing on the database. The accounting function of writing and the customer service function of writing, I thought were appropriate as separate functions. And I really liked the fact that the boss had a robust review back and forth with each of these agents, comma, which were, because they were handling very serious material. I would want this in a commercial setting as well.

Describe three new problems Campus Customs might face that this agent team could solve with the tools you built   
First, drafting pricing negotiations with a vendor. Second, determining pricing for different clothes that have a different cost of goods sold when there is a request for a bulk order. when there is a request for a bulk order. Finally, answering questions about ordering timelines and planning about which payment should go out first.

Describe three new problems Campus Customs might face that this agent team could not solve with the tools you built, and explain the tools and agents you would need to solve them of the desk tickets HTML file. 
problem one would be customer interaction. Problem two would be human review loops. Problem three would be proactive ordering When inventory is low. The first two problems would require a chat window and new database or note-taking fields. So that recent conversations could be parsed by agents. Obviously, the customer-facing chat would require its own website and would land on the customer-facing website, but the user chat could be feasibly added to the desk interface and be between the boss agent and the user. Regarding proactive inventory sourcing, when inventory is low. The first two problems would require a chat window and new database or note-taking fields so that recent conversations could be parsed by agents. Obviously, the customer-facing chat would require its own website (like HW4) and would land on the customer-facing website, but the user chat could be feasibly added to the desk interface and be between the boss agent and the user. In order for proactive tickets (like inventory supplementation) to be made by agents, there would have to be persistent running of heartbeats in the background so that checks were performed, say, on every hour or at the start of every day. The service could be provided by a cloud partner. I envision features coming from other places than new tools and new agents, as I've described above.
3. Stop recording my prompts in the AI_Prompts.md file

## Problem 11: Submit to Github

1. Start recording them again, I changed my mind. We are now on problem 11. create a github repo for this project, name it whatever you like and put the url in output/github_url.txt
