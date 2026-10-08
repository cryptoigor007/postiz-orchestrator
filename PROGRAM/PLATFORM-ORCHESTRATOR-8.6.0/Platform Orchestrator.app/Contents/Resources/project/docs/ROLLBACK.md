# Откат
1. systemctl stop orchestrator.service
2. cp backups/data_XXXX.sqlite data/data.sqlite
3. git checkout <tag> при необходимости
4. systemctl start orchestrator.service
5. curl localhost:8080/health
