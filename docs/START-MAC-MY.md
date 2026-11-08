# Mac မှာ Myan OCR Run လုပ်ရန်

## Docker Desktop

Docker Desktop ကို ဖွင့်ပြီး Engine Running ဖြစ်မဖြစ် စစ်ပါ။ Source ZIP ကို Downloads မှာ Extract လုပ်ပြီး Terminal မှာ—

```bash
cd "$HOME/Downloads/Myan-OCR-v0.1.3"
./scripts/start-mac.sh
```

Web UI: http://localhost:8388  
API status: http://localhost:8388/api/health

ရပ်ရန်—

```bash
docker compose down
```

## Docker မသုံးဘဲ Python နဲ့ Run ရန်

```bash
brew install tesseract tesseract-lang
tesseract --list-langs
```

`mya` နဲ့ `eng` ပါရမယ်။ ပြီးရင်—

```bash
cd "$HOME/Downloads/Myan-OCR-v0.1.3"
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8388
```

## Camera

Mac Browser မှာ localhost ကို Camera Permission ပေးပါ။ Phone ကနေ Mac IP ရဲ့ HTTP Address ဖြင့်ဝင်လျှင် Browser Camera API ကို ပိတ်ထားနိုင်ပါတယ်။ ဖုန်း Camera ကို Browser မှာသုံးလိုပါက HTTPS လိုနိုင်ပြီး၊ အခြားနည်းအဖြစ် `Take photo` ကို သုံးပါ။

## Google Cloud

Cloud Vision OCR / Cloud Translation သုံးမယ်ဆိုရင် Cloud Project မှာ သက်ဆိုင်ရာ API နဲ့ Billing ကို အရင်ဖွင့်ပါ။

```bash
cp .env.example .env
# .env ထဲမှာ GOOGLE_CLOUD_API_KEY ကို ဖြည့်ပါ
docker compose up -d --build
```

Cloud Mode ကို ရွေးမှ Image/Text ကို Google ဆီ ပို့ပါတယ်။ Key ကို JavaScript သို့မဟုတ် Git Repository ထဲ မထည့်ပါနဲ့။

## Ollama Translation

Ollama Install လုပ်ပြီး Model ကို Download လုပ်ပါ—

```bash
ollama pull gemma3:4b
```

Docker သုံးတဲ့အခါ `.env` မှာ—

```dotenv
TRANSLATION_PROVIDER=ollama
OLLAMA_MODEL=gemma3:4b
OLLAMA_URL=http://host.docker.internal:11434
```

ထည့်ပါ။ Native Python Mode မှာ `OLLAMA_URL=http://127.0.0.1:11434` သုံးနိုင်ပါတယ်။

## Tests

```bash
python -m pytest -q
```
