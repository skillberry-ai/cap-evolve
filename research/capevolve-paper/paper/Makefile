PAPER  := paper
PYTHON ?= python3
TEX    := pdflatex -interaction=nonstopmode -halt-on-error

.PHONY: all numbers pending paper check clean

all: numbers pending paper check

numbers:
	$(PYTHON) -I scripts/derive_numbers.py

pending:
	$(PYTHON) -I scripts/mock_numbers.py

paper:
	$(TEX) $(PAPER).tex
	bibtex $(PAPER)
	$(TEX) $(PAPER).tex
	$(TEX) $(PAPER).tex

check: paper
	$(PYTHON) -I scripts/check_paper.py $(PAPER).pdf

clean:
	rm -f $(PAPER).{aux,bbl,blg,log,out,pdf,toc}
