<table>
<tr>
<td valign="top">

## Hi, I'm Ryan 👋

Backend engineer. Most of my time goes into search, RAG, and agents — the part
of the stack you can't really hand-wave, because either the answer is in the
document or it isn't, and anyone can check.

That has shaped how I build. I'd rather measure retrieval than eyeball it, and
I want the reasoning visible, not buried in a prompt. Whatever I ship has to
run on a machine I control.

Java and Python, mostly — Spring Boot on the service side, Elasticsearch when
search is the actual problem.

</td>
<td valign="top" width="400">

<img src="./assets/panel.svg" width="400" alt="Terminal panel: backend engineer, search / RAG / agent, Java and Python, Elasticsearch and Spring Boot, building Anchr in Shanghai, plus GitHub statistics">

</td>
</tr>
</table>

## Anchr

A self-hostable workspace for your own documents. Hybrid search over everything
you've uploaded, answers with citations that link straight to the supporting
passage, and an agent that reads across several steps when one retrieval pass
isn't enough. There's an offline evaluation harness too, because "the model
produced text" is not the same thing as "the answer is in the document."

| Repository | What it is |
| --- | --- |
| **[anchr-app](https://github.com/ryanmeowy/anchr-app)** | Backend: hybrid retrieval, cited answers, agent runs. Java, Spring Boot, Spring AI, Elasticsearch |
| **[anchr-web](https://github.com/ryanmeowy/anchr-web)** | Browser workspace. Next.js, React, Tailwind |
| **[anchr-docling](https://github.com/ryanmeowy/anchr-docling)** | Turns PDFs and office documents into searchable content. Python, Docling, FastAPI |
| **[anchr-eval](https://github.com/ryanmeowy/anchr-eval)** | Offline evaluation, checked against evidence. Python |

🌐 Live demo: **[anchr.cloud](https://anchr.cloud)**  ·  Blog: [ryanyang.cn](https://ryanyang.cn)
