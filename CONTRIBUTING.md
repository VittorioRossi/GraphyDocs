# Contributing to GraphyDocs

Thanks for considering contributing to **GraphyDocs**! This project is still early-stage and evolving fast. Bug reports, feature requests, and pull requests are all welcome.

---

## 📌 Ground Rules

- Be respectful and constructive — follow our [Code of Conduct](./CODE_OF_CONDUCT.md).
- Discuss big changes via Issues before starting on them.
- Keep pull requests focused and minimal.
- If you’re not sure something is needed or wanted, ask first!

---

## 🧰 Project Setup

This project runs entirely via Docker.

### Clone and Run

```bash
git clone https://github.com/VittorioRossi/graphydocs.git
cd graphydocs
cp backend/.env.example backend/.env
docker-compose up -d --build
```
Dev Services

Service	URL
Frontend	http://localhost:5173
Backend	http://localhost:8000
Neo4j	http://localhost:7474

---
📁 Repo Structure

```bash
graphydocs/
├── frontend/   # React + TypeScript
├── backend/    # FastAPI + LSP logic
├── docs/       # Architecture notes
```

---

🧪 Running Tests

⚠️ Note: test coverage is still growing. PRs with tests are highly appreciated.

Backend:

docker-compose exec backend pytest

Frontend:

docker-compose exec frontend npm test


---

📖 Code Style

Python (Backend)
	•	Format with black
	•	Lint with ruff (optional)

JavaScript/TypeScript (Frontend)
	•	Format with prettier
	•	Lint with eslint

npm run format
npm run lint


---

🛠 Opening a Pull Request
	1.	Fork the repository
	2.	Create a new branch (feature/your-change-name)
	3.	Write clear commit messages
	4.	Push your branch and open a PR against main
	5.	Include:
	•	What the change does
	•	Related Issue(s)
	•	Screenshots or examples (if applicable)

---

🏷 Issue Labels

We use the following labels to help guide contributors:
	•	good first issue – easy starter tasks
	•	help wanted – looking for help on this
	•	bug, enhancement, question, etc.

Check the issues tab to find something to work on.

---

🤝 Code of Conduct

All contributors are expected to follow the Code of Conduct.

---

🙏 Thank You

Your contributions make this project better. Whether it’s fixing a typo or building an entire subsystem — you’re helping developers understand their code better.

---
