# LinkedIn PDF to Jake's Resume converter

Convert a LinkedIn-exported PDF resume into a compilable [Jake's Resume](https://github.com/jakegut/resume) LaTeX file. Parsing is local and deterministic. No API key or network connection is required.

## Installation
```bash
pip install -r requirements.txt
```

## Usage
```bash
python main.py resume.pdf
```

or for customized template:
```bash
python main.py Profile.pdf --compile --template data/templates/regyl_template.tex
```
Output is at ./output folder

### Compile
To compile the LaTeX into pdf use:
```bash
python main.py resume.pdf --compile
```
[Executable file for Windows can be obtained here](https://miktex.org/download)  
Compilation uses `pdflatex` when it is on `PATH`, or `xelatex`.