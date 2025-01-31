import json
import openai
import time
import os
import sys
from datetime import datetime
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

openai.api_key = os.getenv("OPENAI_API_KEY")
model_name = os.getenv("OPENAI_MODEL")

# Выбор языка перевода
print("Приложение запущено. Можно начинать перевод с русского языка. На какой язык будем переводить?")
print("EN - английский")
print("CN - китайский")
print("AR - арабский")

language_map = {"EN": "английский", "CN": "китайский", "AR": "арабский"}
language_code = input("Введите код языка (EN, CN, AR): ").strip().upper()

while language_code not in language_map:
    print("Некорректный ввод. Выберите из предложенных вариантов: EN, CN, AR.")
    language_code = input("Введите код языка (EN, CN, AR): ").strip().upper()

print(f"Перевод будет выполнен на {language_map[language_code]} язык.")

start_time = datetime.now()
print(f"Перевод запущен {start_time.strftime('%Y-%m-%d %H:%M:%S')}")

# Прелоадер
def show_loader():
    loader_symbols = ["/", "-", "\\", "-"]
    i = 0
    while translating:
        sys.stdout.write(f"\r{loader_symbols[i % len(loader_symbols)]} Перевод в процессе...")
        sys.stdout.flush()
        time.sleep(0.5)
        i += 1

# Функция для рекурсивного поиска строк для перевода
def extract_texts(data, path=""):
    texts = []
    paths = []
    
    if isinstance(data, dict):
        for key, value in data.items():
            new_path = f"{path}.{key}" if path else key
            sub_texts, sub_paths = extract_texts(value, new_path)
            texts.extend(sub_texts)
            paths.extend(sub_paths)
    elif isinstance(data, list):
        for i, item in enumerate(data):
            new_path = f"{path}[{i}]"
            sub_texts, sub_paths = extract_texts(item, new_path)
            texts.extend(sub_texts)
            paths.extend(sub_paths)
    elif isinstance(data, str):
        texts.append(data)
        paths.append(path)
    
    return texts, paths

# Функция для перевода текста через OpenAI
def translate_texts(texts, batch_size=50):
    global translating
    translating = True
    import threading
    loader_thread = threading.Thread(target=show_loader)
    loader_thread.start()
    
    translations = []
    failed_batches = []
    batch_number = 1
    total_batches = (len(texts) // batch_size) + (1 if len(texts) % batch_size > 0 else 0)
    
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i+batch_size]
        print(f"Отправлен батч №{batch_number}/{total_batches}")
        batch_number += 1
        
        prompt = (f"Переведи следующий текст с русского на {language_map[language_code]}, учитывая, что это медицинское приложение. "
                  "Термины должны оставаться медицинскими, но перевод должен быть понятным пользователю.\n\n" + 
                  "\n".join(batch))
        
        try:
            response = openai.ChatCompletion.create(
                model=model_name,
                messages=[{"role": "system", "content": prompt}],
                temperature=0.5
            )
            
            translated_batch = response["choices"][0]["message"]["content"].split("\n")
            translations.extend(translated_batch)
        except Exception as e:
            print(f"Ошибка при обработке пакета {i}-{i+batch_size}: {str(e)}")
            failed_batches.append((i, batch))
        
        time.sleep(1)
    
    translating = False
    loader_thread.join()
    sys.stdout.write("\rПеревод завершён!\n")
    
    if failed_batches:
        print("Некоторые пакеты не были переведены. Повторная попытка...")
        for i, batch in failed_batches:
            print(f"Повторная обработка пакета {i // batch_size + 1}/{total_batches}...")
            try:
                response = openai.ChatCompletion.create(
                    model=model_name,
                    messages=[{"role": "system", "content": "\n".join(batch)}],
                    temperature=0.5
                )
                translated_batch = response["choices"][0]["message"]["content"].split("\n")
                translations[i:i+batch_size] = translated_batch
            except Exception as e:
                print(f"Ошибка повторной обработки пакета {i}-{i+batch_size}: {str(e)}")
    
    return translations

# Загружаем JSON
with open("ru.json", "r", encoding="utf-8") as f:
    data = json.load(f)

# Извлекаем текст
texts, paths = extract_texts(data)

# Переводим текст
translated_texts = translate_texts(texts)

# Обновляем JSON с переводом
def update_json(data, paths, translations):
    for path, translation in zip(paths, translations):
        keys = path.replace("[", ".").replace("]", "").split(".")
        ref = data
        for key in keys[:-1]:
            if key.isdigit():
                key = int(key)
            ref = ref[key]
        last_key = keys[-1]
        if last_key.isdigit():
            last_key = int(last_key)
        ref[last_key] = translation
    return data

translated_data = update_json(data, paths, translated_texts)

# Формируем имя файла перевода
output_filename = f"{language_code.lower()}.json"

# Сохраняем результат
with open(output_filename, "w", encoding="utf-8") as f:
    json.dump(translated_data, f, ensure_ascii=False, indent=2)

end_time = datetime.now()
print(f"Перевод занял: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
print(f"Файл {output_filename} создан.")