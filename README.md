# SafeSort

SafeSort — программа для безопасной сортировки файлов по папкам.

## Что она делает

SafeSort сканирует каталог, раскладывает файлы по категориям (документы,
изображения, архивы и так далее) и находит файлы с одинаковым содержимым.
Она никогда не меняет файлы без явной команды: `scan`, `plan` и
`duplicates` только показывают, что происходит и что могло бы произойти;
менять файлы умеют только `apply` и `undo`.

## Установка

```bash
git clone https://github.com/Cartesian-School/safesort.git
cd safesort
pip install -e .
```

## Использование

```bash
safesort scan ~/Downloads
safesort plan ~/Downloads
safesort apply ~/Downloads
safesort duplicates ~/Downloads
safesort undo ~/Downloads
```

`scan`, `plan` и `duplicates` — только читают файловую систему. `apply`
перемещает файлы в `Sorted/<категория>/` и записывает JSON-манифест
операции; `undo` читает этот манифест и возвращает файлы туда, откуда
они были взяты.

## Безопасность

- поведение по умолчанию не меняет ни одного файла;
- `apply` никогда не перезаписывает существующий файл молча — при
  конфликте имён находит свободное имя (`report (1).pdf`);
- поиск дубликатов — только отчёт: программа не удаляет ни одного файла
  сама;
- совпадение SHA-256 подтверждается побайтовым сравнением, прежде чем
  файлы считаются дубликатами.

## Тесты

```bash
pip install -e ".[dev]"
pytest tests/
```

## Курс

SafeSort — сквозной проект главы 23 курса [«Python с нуля»
(Cartesian School)](https://github.com/Cartesian-School/python-from-zero),
где показан весь путь его разработки — от идеи до релиза — через
реальные Issue, ветки, Pull Request и GitHub Actions в этом репозитории.

## Лицензия

MIT — см. [LICENSE](LICENSE).
