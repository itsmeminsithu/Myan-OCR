# Test report — v0.1.3

## Automated checks

- `python -m pytest -q`: 54 tests passed in the release test environment.
- Python compile and JavaScript syntax checks passed.
- API tests cover request validation, mock cloud-provider errors, PDF/batch boundaries, host checks and job budgets.
- Earlier browser UI checks used a simulated API. They do not verify real cloud access or physical phone cameras.

## OCR sample

- Printed Pyidaungsu synthetic image: 5.71% character error rate; 0/1 exact matches.
- The sample is too small to make claims about general Myanmar OCR accuracy.

## Not verified

- Full Docker image build on Mac
- Real Google Vision and Google Translation credentials, billing and requests
- Ollama translation with a downloaded model
- iPhone Safari/Android camera capture and mobile cropping
- Public production authentication, network limits and load handling
- Broad evaluation with real Myanmar documents, handwriting and poor lighting

Use `python scripts/benchmark.py samples/benchmark-synthetic.jsonl` to reproduce the supplied sample measurement where the necessary OCR language models are installed.
