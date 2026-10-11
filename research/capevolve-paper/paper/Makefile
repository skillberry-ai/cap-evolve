PAPER  := paper
PYTHON ?= python3
MODE   ?= mock
TEX    := pdflatex -interaction=nonstopmode -halt-on-error

.PHONY: all numbers pending results paper check clean

all: numbers results paper check

numbers:
	$(PYTHON) -I scripts/derive_numbers.py

results:
	sh scripts/build_results.sh $(MODE)

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
