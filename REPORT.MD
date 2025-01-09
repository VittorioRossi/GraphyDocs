# GraphyDocs: Making Code Structure Visual

I built GraphyDocs to help developers better understand their codebases by turning them into interactive graphs. It's written in Python and TypeScript/React, and uses the Language Server Protocol (LSP) as its foundation – which means it can potentially work with any programming language(right now I only tested it on python codebases and with "CONTAINS" relationships)

The system runs on a FastAPI backend that talks to a React frontend through WebSockets, giving users real-time updates as it analyzes their code. I went with Neo4j for storing the graph relationships and Postgres for handling user sessions and project data. Everything runs in Docker containers to keep deployment simple.

While I originally planned to focus purely on the graph mapping algorithm, I got excited about watching the graphs build in real-time. This led me to develop a more complex system that could handle live updates, caching, and database storage. The WebSocket implementation lets users see nodes and edges appear as their code is being analyzed.

The biggest headaches were managing WebSockets and handling asynchronous operations. Getting real-time updates to work smoothly was tricky – I had to carefully handle WebSocket connections, disconnections, and reconnections without losing analysis progress. The async nature of everything made it extra spicy – you've got the code analysis running in the background while trying to keep the WebSocket connection alive and responsive.

Making sure resources got cleaned up properly was another challenge. When a user disconnects or an analysis finishes, you need to make sure everything gets disposed of correctly – otherwise, you end up with memory leaks or hanging connections. I spent a good chunk of time making sure the system could gracefully handle these scenarios without falling apart.

Right now, GraphyDocs works well with Python code and lays the groundwork for some interesting AI-based analysis features I want to add. The graph visualization could use some optimization for larger codebases, but the core functionality is solid and ready for expansion.

I've got several ideas I want to explore with this foundation. The most exciting one is using LLMs to analyze the code graphs and generate smarter documentation. I want to integrate LSP completely and create a more general code mappning algorithm. Furthermore I would like to be able to also connect a web code editor next to the graph visualization so that one can easily interact with graph/written code and see hwo the two version interact with eachother.