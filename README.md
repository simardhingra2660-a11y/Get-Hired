# Get-Hired

**The problem:**
The problem. A serious search means LinkedIn plus hundreds of career pages, VC portfolio boards and niche job sites, then judging each JD against the CV, finding a hiring manager and writing a note that does not read like a template. Most tools scrape titles and score them crudely, or auto-apply at volume. I wanted the opposite: fewer, better-matched roles and honest, specific outreach, on a free-tools-first budget and a 16 GB laptop.
Where it stands (3 Nov 2026).
• Agent: running end to end on my machine, with search, gating, scoring, review, contacts, drafting, Excel export and inbox tracking.
• Evals: 55 offline regression checks pass (up from 42 of 52 when the latest failure reports came in), plus a per-run quality log. 12 real dead links are queued for a live run on my machine.
• Next: a golden set of my approve and reject decisions to evaluate the LLM's relevance judgement, then a Streamlit app (planned, not built).
I acted as user, PM and builder. The rest of this page shows how it works, how I evaluate it, and the cost, latency, security, accuracy and product trade-offs behind it.





**Flow & Architecture:**


<img width="380" height="359" alt="image" src="https://github.com/user-attachments/assets/90a2e2bf-45f9-4978-ad8d-6e7aa16b4b13" />





**Agentic Eval**

Agentic evaluations
The eval suite is failure-driven: every bad result I saw in a real run became a regressioncase before the fix was written, so a problem that was fixed cannot quietly come back. Itnow holds 55 offline checks, all passing.

How I categorise agent evals.
I use three axes:
-what is tested (a single component or tool,the agent's trajectory through routing and fallbacks, or the end-to-end outcome),
-how it is judged (code-based asserts, an LLM-as-judge, or a human), and
-when it runs (offline before or after a change, or online on live runs).



<img width="389" height="271" alt="image" src="https://github.com/user-attachments/assets/63645ed1-7e47-43da-ba62-b42e19c79949" />







<img width="383" height="205" alt="image" src="https://github.com/user-attachments/assets/255a1801-f43c-44b7-a800-3aa394c097ca" />








**The Decision & The Why:**




<img width="382" height="411" alt="image" src="https://github.com/user-attachments/assets/cc5aa78b-a4d6-4483-80a5-6d90cac3d502" />







**Models & Tools: cost, latency, accuracy & security**



<img width="387" height="392" alt="image" src="https://github.com/user-attachments/assets/33f61eb7-d569-428d-8bcf-84c0cbde9acc" />





<img width="388" height="365" alt="image" src="https://github.com/user-attachments/assets/70c1dc36-c267-42f5-bd13-7340201ea7cd" />





<img width="389" height="298" alt="image" src="https://github.com/user-attachments/assets/822bdbe8-deea-437b-960a-14935c52640a" />








