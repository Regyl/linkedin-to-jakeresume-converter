# LinkedIn PDF to Jake's Resume converter

Convert a LinkedIn-exported PDF resume into a compilable [Jake's Resume](https://github.com/jakegut/resume) LaTeX file. Parsing is local and deterministic. No API key or network connection is required.

## Installation
```bash
pip install -r requirements.txt
```

## Usage

Copy the example environment file and set your resume path:

```bash
cp .env.example .env
```

```env
PDF_PATH=resume.pdf
COMPILE=false
TEMPLATE=
```

Then run:

```bash
python main.py
```

Output is at ./output folder.

`PDF_PATH` is the LinkedIn-exported PDF. `COMPILE=true` compiles the generated `.tex` when `pdflatex` or `xelatex` is installed. `TEMPLATE` is optional and defaults to `data/templates/resume.tex`.

Custom template and compile:

```env
PDF_PATH=Profile.pdf
COMPILE=true
TEMPLATE=data/templates/regyl_template.tex
```

### Compile
Set `COMPILE=true` in `.env`, then run `python main.py`.
[Executable file for Windows can be obtained here](https://miktex.org/download)  
Compilation uses `pdflatex` when it is on `PATH`, or `xelatex`.