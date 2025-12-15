import os
import json
import regex
import argparse


def parse_arguments():
    """
    Парсинг аргументов командной строки.
    
    Returns:
        argparse.Namespace: Объект с аргументами
    """
    parser = argparse.ArgumentParser(
        description='Пакетная замена терминов в текстовых файлах и их названиях',
        epilog='Пример использования: python script.py --terms terms_map.json --source kb_source --target kb_final --log replacements.log'
    )
    
    parser.add_argument(
        '--terms',
        required=True,
        default='terms_map.json',
        help='JSON-файл с картой замены терминов (по умолчанию: terms_map.json)'
    )
    
    parser.add_argument(
        '--source',
        required=True,
        default='knowledge_base_source_reviewed',
        help='Исходная директория с файлами для обработки (по умолчанию: knowledge_base_source_reviewed)'
    )
    
    parser.add_argument(
        '--target',
        required=True,
        default='knowledge_base_final',
        help='Целевая директория для сохранения обработанных файлов (по умолчанию: knowledge_base_final)'
    )
    
    parser.add_argument(
        '--log',
        default='names_index_reviewed-s4.log',
        help='Файл для сохранения лога операций (по умолчанию: names_index_reviewed-s4.log)'
    )
    
    parser.add_argument(
        '--verbose',
        '-v',
        action='store_true',
        help='Подробный вывод в консоль'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Пробный запуск без сохранения файлов'
    )
    
    return parser.parse_args()


# === Регулярное выражение для границ слов ===
# Началом слова считается: пробел, табуляция, \n, ", «, _, (, [, -
START_BOUNDARY_CHARS = r"[\s\t\n\"«_[(\-]"


def load_terms_map_sorted(filepath: str, verbose: bool = False) -> list:
    """
    Загружает и сортирует термины из JSON-файла.
    
    Args:
        filepath: Путь к JSON-файлу с картой терминов
        verbose: Флаг подробного вывода
        
    Returns:
        list: Отсортированный список кортежей (термин, замена)
        
    Raises:
        FileNotFoundError: Если файл не существует
        json.JSONDecodeError: Если файл содержит некорректный JSON
    """
    if verbose:
        print(f"📂 Загрузка карты терминов из {filepath}...")
    
    with open(filepath, "r", encoding="utf-8") as f:
        terms = json.load(f)
    
    # Сортируем по алфавиту (без учёта регистра)
    sorted_terms = sorted(terms.items(), key=lambda x: x[0].lower())
    
    # Обратный порядок для обработки от длинных терминов к коротким
    sorted_terms = list(reversed(sorted_terms))
    
    if verbose:
        print(f"✅ Загружено {len(terms)} терминов")
        
    return sorted_terms


def adjust_case(original: str, replacement: str) -> str:
    """
    Сохраняет регистр первой буквы при замене.
    
    Args:
        original: Оригинальный термин
        replacement: Термин для замены
        
    Returns:
        str: Термин для замены с адаптированным регистром
    """
    if not original or not replacement:
        return replacement
    
    if original[0].isupper():
        return replacement[0].upper() + replacement[1:]
    else:
        return replacement[0].lower() + replacement[1:]


def replace_terms_in_text(text: str, terms: list, verbose: bool = False) -> tuple:
    """
    Заменяет термины в тексте согласно карте замен.
    
    Args:
        text: Исходный текст
        terms: Список кортежей (термин, замена)
        verbose: Флаг подробного вывода
        
    Returns:
        tuple: (изменённый текст, словарь замен)
    """
    replacements_log = {}
    
    if verbose:
        print(f"  🔄 Обработка текста ({len(text)} символов)...")
    
    for key, value in terms:
        key_escaped = regex.escape(key)
        
        # Паттерн для поиска термина в начале слова
        pattern = regex.compile(
            rf"(?i)(?<={START_BOUNDARY_CHARS}|^){key_escaped}(?=\X*)"
        )
        
        def sub_func(match):
            """Функция для замены с сохранением регистра и логированием."""
            matched = match.group(0)
            replaced = adjust_case(matched, value)
            
            # Логирование замены
            replacements_log.setdefault((matched, replaced), 0)
            replacements_log[(matched, replaced)] += 1
            
            return replaced
        
        # Выполняем замену
        text = pattern.sub(sub_func, text)
    
    return text, replacements_log


def replace_terms_in_filename(filename: str, terms: list) -> str:
    """
    Заменяет термины в имени файла.
    
    Args:
        filename: Исходное имя файла
        terms: Список кортежей (термин, замена)
        
    Returns:
        str: Новое имя файла
    """
    name, ext = os.path.splitext(filename)
    
    for key, value in terms:
        key_escaped = regex.escape(key)
        pattern = regex.compile(
            rf"(?i)(?<={START_BOUNDARY_CHARS}|^){key_escaped}(?=\X*)"
        )
        
        def sub_func(match):
            """Функция для замены с сохранением регистра."""
            matched = match.group(0)
            return adjust_case(matched, value)
        
        name = pattern.sub(sub_func, name)
    
    return name + ext


def process_all_files(terms: list, source_dir: str, target_dir: str, 
                      log_file: str, verbose: bool = False, dry_run: bool = False) -> None:
    """
    Обрабатывает все .md файлы в исходной директории.
    
    Args:
        terms: Список кортежей (термин, замена)
        source_dir: Исходная директория
        target_dir: Целевая директория
        log_file: Файл для лога
        verbose: Флаг подробного вывода
        dry_run: Флаг пробного запуска
    """
    log_lines = []
    processed_count = 0
    total_replacements = 0
    
    # Создаём целевую директорию (если не dry-run)
    if not dry_run:
        os.makedirs(target_dir, exist_ok=True)
    
    # Получаем список файлов
    files = [f for f in os.listdir(source_dir) if f.endswith(".md")]
    
    if not files:
        message = f"⚠️  В исходной директории {source_dir} не найдено .md файлов."
        log_lines.append(message)
        print(message)
        return
    
    if verbose:
        print(f"📁 Найдено {len(files)} .md файлов для обработки")
    
    for filename in files:
        source_path = os.path.join(source_dir, filename)
        
        try:
            # Читаем исходный файл
            with open(source_path, "r", encoding="utf-8") as f:
                original_text = f.read()
            
            # Заменяем термины в тексте
            updated_text, replacements = replace_terms_in_text(original_text, terms, verbose)
            
            # Заменяем термины в имени файла
            new_filename = replace_terms_in_filename(filename, terms)
            target_path = os.path.join(target_dir, new_filename)
            
            # Сохраняем изменённый файл (если не dry-run)
            if not dry_run:
                with open(target_path, "w", encoding="utf-8") as f:
                    f.write(updated_text)
            
            # Формируем лог для этого файла
            filename_changed = (new_filename != filename)
            if filename_changed:
                log_lines.append(f"📄 Файл: {filename} → {new_filename}")
                if verbose:
                    print(f"  📝 {filename} → {new_filename}")
            else:
                log_lines.append(f"📄 Файл: {filename} (без изменений в имени)")
                if verbose:
                    print(f"  📝 {filename}")
            
            file_total = 0
            for (orig, repl), count in sorted(replacements.items()):
                log_lines.append(f"  🔄 Заменено: '{orig}' → '{repl}' ({count} раз(а))")
                file_total += count
                total_replacements += count
            
            log_lines.append(f"  📊 Всего замен в файле: {file_total}\n")
            processed_count += 1
            
            if verbose and file_total > 0:
                print(f"    🔄 {file_total} замен")
            
        except Exception as e:
            error_msg = f"❌ Ошибка при обработке файла {filename}: {str(e)}"
            log_lines.append(error_msg)
            print(error_msg)
            continue
    
    # Добавляем сводную информацию
    summary = [
        "\n" + "="*50,
        "СВОДНАЯ ИНФОРМАЦИЯ:",
        f"Обработано файлов: {processed_count}/{len(files)}",
        f"Всего замен: {total_replacements}",
        f"Исходная директория: {source_dir}",
        f"Целевая директория: {target_dir}",
        f"Режим dry-run: {'ДА' if dry_run else 'НЕТ'}",
        "="*50
    ]
    
    log_lines.extend(summary)
    
    # Сохраняем лог (если не dry-run или явно указан файл лога)
    if not dry_run:
        try:
            with open(log_file, "w", encoding="utf-8") as f:
                f.write("\n".join(log_lines))
            if verbose:
                print(f"📝 Лог сохранён в {log_file}")
        except Exception as e:
            print(f"❌ Ошибка при сохранении лога: {str(e)}")
    elif verbose:
        print("📝 Лог не сохранён (режим dry-run)")
    
    # Выводим сводку в консоль
    print("\n" + "="*50)
    print(f"📊 СВОДКА:")
    print(f"  Обработано файлов: {processed_count}/{len(files)}")
    print(f"  Всего замен: {total_replacements}")
    print(f"  Целевая директория: {target_dir}")
    if dry_run:
        print(f"  ⚠️  РЕЖИМ DRY-RUN - файлы не сохранены")
    print("="*50)


def validate_environment(terms_file: str, source_dir: str) -> bool:
    """
    Проверяет наличие необходимых файлов и директорий.
    
    Args:
        terms_file: Путь к файлу с терминами
        source_dir: Путь к исходной директории
        
    Returns:
        bool: True если все проверки пройдены
    """
    checks = []
    
    # Проверяем файл с терминами
    if not os.path.exists(terms_file):
        checks.append(f"❌ Файл {terms_file} не найден")
    
    # Проверяем исходную директорию
    if not os.path.exists(source_dir):
        checks.append(f"❌ Директория {source_dir} не найдена")
    elif not os.path.isdir(source_dir):
        checks.append(f"❌ {source_dir} не является директорией")
    
    # Выводим результаты проверок
    if checks:
        print("\n".join(checks))
        return False
    
    return True


def print_configuration(args):
    """Выводит конфигурацию скрипта."""
    print("⚙️  Конфигурация скрипта:")
    print(f"  Файл с терминами: {args.terms}")
    print(f"  Исходная директория: {args.source}")
    print(f"  Целевая директория: {args.target}")
    print(f"  Файл лога: {args.log}")
    print(f"  Подробный вывод: {'ДА' if args.verbose else 'НЕТ'}")
    print(f"  Режим dry-run: {'ДА' if args.dry_run else 'НЕТ'}")


def main():
    """
    Основная функция скрипта.
    """
    # Парсим аргументы
    args = parse_arguments()
    
    print("🚀 Запуск скрипта замены терминов")
    print("="*50)
    
    # Показываем конфигурацию
    print_configuration(args)
    print("="*50)
    
    # Проверяем окружение
    if not validate_environment(args.terms, args.source):
        print("\n❌ Проверка окружения не пройдена. Скрипт завершён.")
        exit(1)
    
    try:
        # Загружаем и сортируем термины
        terms = load_terms_map_sorted(args.terms, args.verbose)
        
        # Обрабатываем файлы
        print("\n🔄 Обработка файлов...")
        process_all_files(
            terms=terms,
            source_dir=args.source,
            target_dir=args.target,
            log_file=args.log,
            verbose=args.verbose,
            dry_run=args.dry_run
        )
        
        if not args.dry_run:
            print("\n✅ Обработка завершена успешно!")
        
    except json.JSONDecodeError as e:
        print(f"\n❌ Ошибка в формате JSON файла {args.terms}: {str(e)}")
        exit(1)
    except Exception as e:
        print(f"\n❌ Неожиданная ошибка: {str(e)}")
        exit(1)


# === Точка входа ===
if __name__ == "__main__":
    main()