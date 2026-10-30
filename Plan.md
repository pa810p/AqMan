# Aquarium Manager — Implementation Plan

## 1. Cel projektu

Stworzenie lokalnej aplikacji webowej do zarządzania wieloma akwariami słodkowodnymi.

Aplikacja ma zastąpić arkusz kalkulacyjny wykorzystywany do zapisywania:
- parametrów wody;
- notatek i obserwacji;
- nawożenia i innych działań pielęgnacyjnych;
- historii zmian parametrów;
- obliczeń przewidywanych zmian stężeń po dodaniu nawozów.

Głównym celem jest wygodne prowadzenie historii każdego akwarium oraz wykonywanie obliczeń związanych z jego utrzymaniem.

## 2. Technologie

- Python 3.12+
- NiceGUI — interfejs użytkownika.
- SQLAlchemy 2.x — ORM i dostęp do bazy.
- SQLite — lokalna baza danych.
- Alembic — migracje schematu bazy.
- pytest — testy jednostkowe i integracyjne.
- Plotly — wykresy historyczne.

Nie używać React, Node.js jako osobnego backendu, PostgreSQL ani Dockera na pierwszym etapie.

## 3. Architektura

Zastosować separację warstw:

- UI — prezentacja danych i obsługa interakcji.
- Services — logika biznesowa i obliczenia.
- Models — modele SQLAlchemy.
- Repositories — dostęp do danych.
- Database — konfiguracja silnika i sesji.
- Tests — testy.

Logika obliczeniowa nie może zależeć od NiceGUI ani od interfejsu użytkownika.

Przewidzieć możliwość późniejszego zastąpienia interfejsu lub dodania API bez konieczności przepisywania logiki biznesowej.

## 4. Model danych

### Aquarium
- id
- name
- volume_liters
- description
- created_at
- active

### Parameter
Definicje parametrów wody:
- id
- name (NO3, PO4, pH, KH, GH, temperature itd.)
- unit
- description

Nie zakładać, że wszystkie akwaria mają identyczny zestaw mierzonych parametrów.

### MeasurementSession
Reprezentuje zapis konkretnego pomiaru w konkretnym akwarium:
- id
- aquarium_id
- timestamp
- general_note (opcjonalnie)

### Measurement
Pojedynczy wynik pomiaru:
- id
- session_id
- parameter_id
- value
- note (opcjonalnie)

W MVP formularz zapisuje jeden parametr i jedną wartość na raz. Wewnętrzny rekord MeasurementSession grupuje pojedynczy pomiar; drugi parametr można od razu zapisać osobno z osobnym timestampem.

### Note
- id
- aquarium_id
- timestamp
- category (opcjonalnie)
- content

Notatki powinny być możliwe do dodania niezależnie od pomiarów.

### Fertilizer
- id
- name
- description
- active
- skład i stężenia poszczególnych substancji odżywczych

Model składu powinien umożliwiać definiowanie wielu składników w jednym preparacie.

### FertilizerComponent
- id
- fertilizer_id
- parameter_id
- concentration
- concentration_unit

Jednostki i sposób interpretacji stężeń muszą być jednoznacznie określone.

### Dosing
- id
- aquarium_id
- fertilizer_id
- timestamp
- amount
- amount_unit
- calculated_effect (opcjonalnie, jeśli potrzebne do zachowania historycznego wyniku obliczeń)
- note

Rejestrować faktycznie wykonaną dawkę, nie tylko planowaną.

### WaterChange
- id
- aquarium_id
- timestamp
- volume_liters
- water_source
- description

W MVP źródło wody przyjmuje wartości RO, kran lub mieszane. Rejestrowana jest ilość w litrach; parametry wody źródłowej i obliczanie wpływu podmiany są poza zakresem MVP.

## 5. Logika obliczeniowa

Wydzielić obliczenia do niezależnego modułu.

Podstawowe funkcjonalności:

1. Obliczanie przewidywanego wzrostu stężenia danego parametru po dodaniu określonej ilości nawozu.
2. Obliczanie przewidywanego stężenia końcowego.
3. Uwzględnianie objętości akwarium.
4. Obsługa nawozów zawierających kilka składników.
5. Obsługa różnych jednostek i konwersji.
6. Możliwość porównania przewidywanych wartości z kolejnymi pomiarami.

Ważne:
- Nie nadpisywać wyników pomiarów wartościami obliczonymi.
- Rozróżniać wartości zmierzone i przewidywane.
- Nie zakładać, że obliczone stężenie jest równe rzeczywistemu stężeniu w akwarium.
- Zachować parametry nawozu i dane wejściowe wykorzystane do historycznego obliczenia, aby późniejsza zmiana definicji preparatu nie zmieniała historii.
- Nie implementować wzorów chemicznych na podstawie domysłów. Najpierw przeanalizować dotychczasowe obliczenia użytkownika.

## 6. Interfejs użytkownika

Domyślnym językiem interfejsu jest angielski; język można przełączyć na polski z poziomu górnego paska aplikacji.

### Dashboard
- Lista wszystkich aktywnych akwariów.
- Ostatni pomiar i data pomiaru.
- Podstawowe informacje o każdym zbiorniku.
- Wybranie akwarium otwiera jego szczegółowy widok.
- Informacja, kiedy ostatnio aktualizowano dane.

Nie wymuszać regularnych pomiarów ani harmonogramu.

### Widok akwarium
- Dane podstawowe.
- Siatka formularzy: dodawanie pomiaru, podmiany wody i notatki; obok notatki pozostaje miejsce na przyszłą funkcję.
- Jedna tabela historii grupująca wpisy według daty, z kolumnami parametrów, podmian i notatek.
- Kilka wyników tego samego parametru w jednym dniu jest prezentowanych razem.
- Każdy wynik w historii można otworzyć do edycji; zmiana obejmuje datę, parametr, wartość i notatkę.
- Skróty notatek otwierają edycję, a po najechaniu pokazują pełną treść; notatki przy pomiarach otwierają edycję tego pomiaru.
- Wpisy podmian w historii otwierają edycję daty, źródła, ilości i opisu.
- Historia nawożenia.
- Wykresy wybranych parametrów.
- Dane i formularze dotyczą wyłącznie akwarium otwartego z dashboardu i są dostępne w jednym widoku.

### Formularz pomiaru
- Akwarium wynika z aktualnie otwartego widoku akwarium.
- Data i godzina (domyślnie bieżąca).
- Wybór jednego parametru z comboboxa i wprowadzenie jego wartości.
- Możliwość dodania notatki do pomiaru.
- Zapis pojedynczego pomiaru; kolejny parametr wprowadza się w osobnym zapisie.

### Formularz nawożenia
- Wybór akwarium.
- Wybór preparatu.
- Ilość nawozu.
- Automatyczne obliczenie przewidywanej zmiany stężeń.
- Pokazanie wartości przed i po dodaniu nawozu.
- Zatwierdzenie wykonanej dawki.

Formularz nawożenia i powiązane obliczenia są poza zakresem pierwszego prototypu..

### Historia i wykresy
- Wybór parametru.
- Zakres czasu.
- Prezentacja pomiarów na wykresie.
- Możliwość odróżnienia pomiarów rzeczywistych od wartości obliczonych.
- Widok zdarzeń nawożenia i podmian na osi czasu.

W MVP historia obejmuje pomiary, notatki i zarejestrowane podmiany. Wykresy oraz obliczenia wpływu podmian pozostają na późniejszy etap..

### Ustawienia
- Zarządzanie akwariami.
- Zarządzanie parametrami.
- Zarządzanie nawozami i ich składem.

## 7. Wymagania techniczne

- Wszystkie daty przechowywać w jednoznacznym formacie, z poprawną obsługą strefy czasowej.
- Zapewnić integralność relacji i transakcyjność operacji bazodanowych.
- Stosować migracje Alembic.
- Walidować dane wejściowe.
- Obsługiwać błędy bez utraty danych.
- Nie wykonywać zapytań do bazy bezpośrednio w komponentach UI.
- Konfigurację aplikacji przechowywać poza kodem.
- Baza danych powinna znajdować się w trwałym katalogu danych, niezależnym od katalogu instalacyjnego aplikacji.
- Przygotować mechanizm kopii zapasowych SQLite.
- Nie wystawiać aplikacji publicznie w Internecie. Początkowo dostęp wyłącznie przez lokalną sieć.
- Interfejs powinien być responsywny i wygodny na ekranie telefonu.

## 8. Testy

Priorytetem są testy logiki obliczeniowej.

Przygotować testy dla:
- przeliczania dawek nawozów;
- konwersji jednostek;
- różnych objętości akwariów;
- nawozów zawierających kilka składników;
- obliczeń po podmianie wody;
- poprawności zapisu i odczytu historii;
- migracji bazy danych.

Testy obliczeniowe muszą wykorzystywać jawnie określone dane wejściowe i oczekiwane wyniki.

## 9. Etapy implementacji

### Etap 1 — Fundament
- Struktura projektu.
- Konfiguracja SQLAlchemy i SQLite.
- Modele danych.
- Migracje Alembic.
- Testy warstwy danych.

### Etap 2 — Podstawowa aplikacja
- Dashboard.
- Zarządzanie akwariami.
- Zarządzanie definicjami parametrów.
- Dodawanie sesji pomiarowych.
- Notatki.
- Historia pomiarów.
- Rejestrowanie podmian: źródło RO/kran/mieszane i ilość w litrach.

### Etap 3 — Nawożenie i obliczenia (poza MVP)
- Definicje nawozów.
- Skład preparatów.
- Rejestrowanie dawek.
- Obliczanie przewidywanych zmian stężeń.
- Testy obliczeniowe.

### Etap 4 — Podmiany wody i historia
- Parametry wody użytej do podmiany.
- Obliczanie wpływu podmiany na parametry.
- Wykresy historyczne.
- Zestawienie zdarzeń i pomiarów.

### Etap 5 — Użyteczność i wdrożenie
- Responsywny interfejs mobilny.
- Eksport i import danych.
- Kopie zapasowe.
- Dokumentacja uruchomienia.
- Testy całościowe.

## 10. Zasady realizacji

- Implementować etapami, nie generować całej aplikacji jednorazowo.
- Przed implementacją przedstawić model danych i uzgodnić go z użytkownikiem.
- Uzgodniony zakres MVP: dashboard, akwaria, parametry, pomiary, notatki oraz rejestrowanie podmian; bez nawożenia i obliczeń.
- MVP działa lokalnie przez przeglądarkę lub w oknie standalone NiceGUI/pywebview. Dostęp sieciowy można włączyć parametrem uruchomienia.
- Nie dodawać funkcjonalności, które nie wynikają z wymagań.
- Nie komplikować architektury przed pojawieniem się rzeczywistej potrzeby.
- Zachować czytelność, typowanie i testowalność kodu.
- Każdy etap powinien kończyć się działającą wersją aplikacji i testami.
- Nie wprowadzać przykładowych danych do właściwej bazy użytkownika.
- Nie podejmować decyzji dotyczących wzorów obliczeniowych bez potwierdzenia ich poprawności.