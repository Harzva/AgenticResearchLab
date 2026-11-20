# Public catalog sources

`manifest.json` locks the public metadata used by the offline build. For a conference source update, check the new upstream catalog at an immutable commit, update its commit URL, SHA-256 and record count, then run `python -m unittest discover -s tests -v`.

The CVPR snapshot is the original public Git blob from `Harzva/awesome-ai-paper-notes`. Chinese strings are the source's reading-note titles. The snapshot does not contain published WeChat URLs or article text.

The TPAMI starter collection uses IEEE's publication records and Crossref's publisher-deposited bibliographic data. Its years refer to the journal issue. The three public PDF links point to author preprints on arXiv, and the short English summaries paraphrase the public abstracts. Keep unknown fields null. Update the checksum and record count in the manifest when adding a publisher-verified record.
