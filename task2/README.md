# Задание 2. Подготовка базы знаний

## За основу взята вселенная Star Wars. Источник данных: "https://starwars.fandom.com"

## Парсинг сайта запускается скриптом `fetch_data.py`. Для работы обязательно указать каталог сохранения файлов, аргумент `--out`. Предварительно следует установить зависимости из `requirements.txt`.
```
cd task2
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python fetch_data.py --out ./raw
```
В результате в директории kb будут лежать исходные md файлы базы знаний

## Замена ключевых терминов (персонажей, планет, технологии) на вымышленные названия.
Маппинг терминов `terms_map.json` собран вручную.
Замена терминов выполняется скриптом `replace_data.py` 
```
cd task2
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python replace_data.py --source raw --target kb --terms terms_map.json
```

Лог замен пишется в файл `names_index_reviewed-s4.log`.