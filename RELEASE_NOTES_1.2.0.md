# LisiCode 1.2.0 — изменения

- Добавлена основа Connections и рабочее подключение GitHub через PAT.
- Добавлена публикация проекта в новый публичный GitHub-репозиторий с подтверждением и базовой проверкой секретов.
- Добавлена команда отключения GitHub и отображение статуса подключений.
- Лимит агентского цикла увеличен с 30 до 300 циклов; добавлена защита от многократного повтора одинакового вызова инструмента.
- Подправлено управление вводом: во время выполнения задачи приглашение обычного ввода скрывается; подтверждения получают отдельный prompt.
- Ошибочные результаты инструментов и ненулевые exit code выводятся как ERROR.
- XP теперь начисляется по правилу 1 буква = 1 XP; пробелы, цифры и знаки пунктуации не учитываются.
- Добавлены честные ограничения по Gmail/Google/MCP: они пока не подключены.


## 1.2.2 Connection input hotfix
- Fixed the CLI input lock after local slash commands: the keyboard reader is re-enabled after `/connections`, `/chat`, `/memory`, and other local commands.
- All unknown `/connections ...` subcommands now show local usage and never reach the model.
