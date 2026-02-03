# Contributing to BitAxe Discord Status Bot

Vielen Dank für dein Interesse, zu diesem Projekt beizutragen! 🎉

## 🐛 Bug Reports

Wenn du einen Bug gefunden hast:
1. Überprüfe, ob das Problem bereits als Issue gemeldet wurde
2. Erstelle ein neues Issue mit:
   - Detaillierter Beschreibung des Problems
   - Schritten zur Reproduktion
   - Erwartetes vs. tatsächliches Verhalten
   - Log-Ausgaben (falls verfügbar)
   - System-Informationen (Python-Version, OS)

## ✨ Feature Requests

Feature-Vorschläge sind willkommen! Bitte:
1. Überprüfe, ob das Feature bereits vorgeschlagen wurde
2. Erstelle ein Issue mit:
   - Klarer Beschreibung des Features
   - Use Case / Motivation
   - Mögliche Implementierungs-Ideen

## 🔧 Pull Requests

### Setup für Entwicklung

```bash
# Repository forken und klonen
git clone https://github.com/dein-username/bitaxe-discord-status-bot.git
cd bitaxe-discord-status-bot

# Virtual Environment erstellen
python -m venv venv
source venv/bin/activate  # Linux/Mac
# oder
venv\Scripts\activate  # Windows

# Dependencies installieren
pip install -r requirements.txt

# Config erstellen
cp config.ini.example config.ini
# Bearbeite config.ini mit deinen Werten
```

### Code-Stil

- Verwende Python 3.10+ Features
- Folge PEP 8 Style Guide
- Füge Docstrings zu Funktionen hinzu
- Kommentiere komplexe Logik
- Verwende Type Hints wo möglich

### Commit-Messages

Folge dem [Conventional Commits](https://www.conventionalcommits.org/) Format:

```
feat: Neue Feature-Beschreibung
fix: Bug-Fix-Beschreibung
docs: Dokumentations-Änderung
refactor: Code-Refactoring
test: Test-Änderungen
chore: Build-/Tool-Änderungen
```

Beispiele:
```
feat: Füge NerdMiner V2 Unterstützung hinzu
fix: Behebe Division durch Null bei Offline-Geräten
docs: Aktualisiere Docker-Anleitung in README
```

### Pull Request Prozess

1. **Branch erstellen**
   ```bash
   git checkout -b feature/deine-feature-beschreibung
   ```

2. **Änderungen committen**
   ```bash
   git add .
   git commit -m "feat: Beschreibung"
   ```

3. **Pushen**
   ```bash
   git push origin feature/deine-feature-beschreibung
   ```

4. **Pull Request öffnen**
   - Beschreibe deine Änderungen
   - Verlinke relevante Issues
   - Füge Screenshots hinzu (falls UI-Änderungen)

5. **Code Review**
   - Reagiere auf Feedback
   - Aktualisiere deinen Branch bei Bedarf

### Was zu beachten ist

- ✅ Teste deine Änderungen lokal
- ✅ Aktualisiere die Dokumentation
- ✅ Stelle sicher, dass keine Errors vorliegen
- ✅ Halte PRs fokussiert (eine Feature/Fix pro PR)
- ❌ Committe keine sensiblen Daten (Tokens, IPs)
- ❌ Committe keine generierten Dateien (logs, __pycache__)

## 📂 Projektstruktur

```
src/
├── main.py              # Bot Entry Point & Discord Integration
├── device_status.py     # API Client für BitAxe/NerdAxe
└── status_overview.py   # Status Formatting & Embed Creation

data/                    # Runtime Daten (gitignored)
logs/                    # Log-Dateien (gitignored)
```

## 🧪 Testing

Aktuell gibt es keine automatisierten Tests. Teste manuell:
1. Starte den Bot lokal
2. Überprüfe Discord-Ausgabe
3. Teste mit verschiedenen Geräte-Konfigurationen
4. Teste Error-Szenarien (Offline-Geräte, ungültige IPs)

## 📝 Lizenz

Indem du zu diesem Projekt beiträgst, stimmst du zu, dass deine Beiträge unter der MIT-Lizenz lizenziert werden.

## 💬 Fragen?

Öffne ein Issue oder schreibe eine Nachricht!

Vielen Dank für deine Hilfe! 🚀
