#!/bin/bash

echo "Setup Stanford CoreNLP ..."
cd stanfordnlp
wget http://nlp.stanford.edu/software/stanford-parser-full-2014-01-04.zip 
unzip stanford-parser-full-2014-01-04.zip

echo "Setup Charniak Parser ..."
pip install --user bllipparser
