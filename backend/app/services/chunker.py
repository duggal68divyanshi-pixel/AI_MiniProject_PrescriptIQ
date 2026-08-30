"""
Chunking strategy.

Approach: sentence-aware sliding window.

1. Text is split into sentences (regex-based, avoids extra ML dependency).
2. Sentences are packed into chunks up to `chunk_size_tokens` (approximated
   as whitespace-delimited words, ~0.75 words per GPT-style token in
   English prose, which is a good enough proxy without pulling in a
   tokenizer library).
3. Consecutive chunks overlap by `chunk_overlap_tokens` worth of trailing
   sentences from the previous chunk, so information that sits right at a
   chunk boundary is never lost as context for either the retrieval or the
   generation step.
4. Each chunk records the page number of the sentence it *starts* on so
   citations ("Page 5") remain accurate even when a chunk spans a page
   break.

This keeps chunks semantically coherent (never mid-sentence) while
bounding their size for the embedding model, and the overlap protects
against a fact being split exactly across two chunks and disappearing
from both when a query only weakly matches either half.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.services.pdf_processor import PageText

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'\(])")


@dataclass
class Sentence:
    text: str
    page_number: int


@dataclass
class Chunk:
    chunk_index: int
    text: str
    page_number: int | None
    word_count: int


def _split_into_sentences(pages: list[PageText]) -> list[Sentence]:
    sentences: list[Sentence] = []
    for page in pages:
        # Split on paragraph first so we don't merge unrelated paragraphs
        # into one "sentence" when punctuation is sparse (e.g. headings).
        for para in page.text.split("\n\n"):
            para = para.strip()
            if not para:
                continue
            for sent in _SENTENCE_SPLIT_RE.split(para):
                sent = sent.strip()
                if sent:
                    sentences.append(Sentence(text=sent, page_number=page.page_number))
    return sentences


def _word_count(text: str) -> int:
    return len(text.split())


def chunk_document(
    pages: list[PageText],
    chunk_size_tokens: int = 400,
    chunk_overlap_tokens: int = 80,
) -> list[Chunk]:
    """Produce overlapping, sentence-aligned chunks from extracted page text."""
    sentences = _split_into_sentences(pages)
    if not sentences:
        return []

    chunks: list[Chunk] = []
    current: list[Sentence] = []
    current_words = 0
    chunk_index = 0

    i = 0
    while i < len(sentences):
        sent = sentences[i]
        sent_words = _word_count(sent.text)

        if current and current_words + sent_words > chunk_size_tokens:
            chunk_text = " ".join(s.text for s in current)
            chunks.append(
                Chunk(
                    chunk_index=chunk_index,
                    text=chunk_text,
                    page_number=current[0].page_number,
                    word_count=current_words,
                )
            )
            chunk_index += 1

            # Build overlap: walk backwards from the end of `current` until
            # we've collected ~chunk_overlap_tokens worth of trailing words.
            overlap: list[Sentence] = []
            overlap_words = 0
            for s in reversed(current):
                overlap.insert(0, s)
                overlap_words += _word_count(s.text)
                if overlap_words >= chunk_overlap_tokens:
                    break
            current = overlap
            current_words = overlap_words
            continue  # re-evaluate the same sentence against the new (overlapped) chunk

        current.append(sent)
        current_words += sent_words
        i += 1

    if current:
        chunk_text = " ".join(s.text for s in current)
        chunks.append(
            Chunk(
                chunk_index=chunk_index,
                text=chunk_text,
                page_number=current[0].page_number,
                word_count=current_words,
            )
        )

    return chunks
