# Retrieving data

Brief overview of steps 1 and 2 in `meting_mate/ingest`

## Fetching changes from drive

Call `_1_crawl_drive.py`.

This script loops through all app users and uses the google docs API to locate their own and shared google docs documents. Whenever a new or modified document is discovered, a check against the database is run. If the db timestamp deviates from the Gdocs timestamp (or if the doc is missing altogether), the document is upserted.

# Retrieving data

Brief overview of steps 1 and 2 in `meting_mate/ingest`
## Fetching changes from drive
Call `_1_crawl_drive.py`.
This script loops through all app users and uses the google docs API to locate their own and shared google docs documents. Whenever a new or modified document is discovered, a check against the database is run. If the db timestamp deviates from the Gdocs timestamp (or if the doc is missing altogether), the document is upserted.

[![](https://mermaid.ink/img/pako:eNptkstuwyAQRX8FsW2stFsvIrWK1FWlSt16M4KxQTUMhSFtFOXfi-M8cBSvMPfceXKQijTKVib8yegVbi0MEVznRfk-92zIN5vN0wf5gbZvrcgJYxKFjfuZOSsFamb8zMzqSBRET1HgrjhOyiwswl-MyqD6Fkzf6AX-BRuBLfmbgQLXKuqbVMWb6n0nGkYUr5lNKyL2EZOZrUtLxTV1Cx5_hdX3DvT6QfWXZNtod9iK0SZeBxisB0ahSaWbpybrdBMlHDJoYOiqjHfzG2Z_wR92Xi8qIURlJrQ0sqQfrOy5eTmXukSniXs6RSlFsHWYGFwQziYHrMySXizhWknEMILCdQ5l-zzFyg49L62L0V5_ykGupMPowOrySg_TdSfZoMNOtuWosYc8cic7fywoZKavvVey5ZhxJXMoE7086stlpDwY2fYwJjz-A47v79Y?type=png)](https://mermaid.live/edit#pako:eNptkstuwyAQRX8FsW2stFsvIrWK1FWlSt16M4KxQTUMhSFtFOXfi-M8cBSvMPfceXKQijTKVib8yegVbi0MEVznRfk-92zIN5vN0wf5gbZvrcgJYxKFjfuZOSsFamb8zMzqSBRET1HgrjhOyiwswl-MyqD6Fkzf6AX-BRuBLfmbgQLXKuqbVMWb6n0nGkYUr5lNKyL2EZOZrUtLxTV1Cx5_hdX3DvT6QfWXZNtod9iK0SZeBxisB0ahSaWbpybrdBMlHDJoYOiqjHfzG2Z_wR92Xi8qIURlJrQ0sqQfrOy5eTmXukSniXs6RSlFsHWYGFwQziYHrMySXizhWknEMILCdQ5l-zzFyg49L62L0V5_ykGupMPowOrySg_TdSfZoMNOtuWosYc8cic7fywoZKavvVey5ZhxJXMoE7086stlpDwY2fYwJjz-A47v79Y)


---

Call `_2_get_contents.py`.

This script locates all documents documents with no content from the "docs" collection, then proceeds to download the document contents in multiple formats - native JSON as returned by the google docs API, as well as a MS Word .docx export. The word format is then converted to HTML and Markdown using Mammoth.

[![](https://mermaid.ink/img/pako:eNp9UsFuwjAM_RUr2gE04AN64DChMU3rVokdK02mcduINumSlFEh_n0OFFbGtFyi5_f87NjZi8xIEpFw9NmSzmihsLBYpxr4NGi9ylSD2kMC6CDpfGn0LRkHMja6MIuHW3a5sGpLQbI0pqgIjvgvncncUMYw7asl0_n8Po5ArmeSw7NcaTnap9y-9qR9KiJgdEc75bwL6BErR4fD-JQec_o04fSBZWVMA7mxQJiVgTmFh9Vy8ky1jixgNuDPdhwESR5V5WCEjYINdeNfNsdXRVCQh3OzF8GR672eV2-vt4reIgyMuw_XiuxWZcQTqMiNxjPaNcb6j5qkwqFz0P68egdrpdF2187MccUtWQ_ewNN7_PIfH6PdSPOlrzU8praR6CmUaetL96RlqsVE1GRrVJL_2D4QqfAl1RRWlApJObYVby_VB5Zi682q05mIvG1pIk6-_ZcUUR5WOhHWtEXZo8M3oEfdNg?type=png)](https://mermaid.live/edit#pako:eNp9UsFuwjAM_RUr2gE04AN64DChMU3rVokdK02mcduINumSlFEh_n0OFFbGtFyi5_f87NjZi8xIEpFw9NmSzmihsLBYpxr4NGi9ylSD2kMC6CDpfGn0LRkHMja6MIuHW3a5sGpLQbI0pqgIjvgvncncUMYw7asl0_n8Po5ArmeSw7NcaTnap9y-9qR9KiJgdEc75bwL6BErR4fD-JQec_o04fSBZWVMA7mxQJiVgTmFh9Vy8ky1jixgNuDPdhwESR5V5WCEjYINdeNfNsdXRVCQh3OzF8GR672eV2-vt4reIgyMuw_XiuxWZcQTqMiNxjPaNcb6j5qkwqFz0P68egdrpdF2187MccUtWQ_ewNN7_PIfH6PdSPOlrzU8praR6CmUaetL96RlqsVE1GRrVJL_2D4QqfAl1RRWlApJObYVby_VB5Zi682q05mIvG1pIk6-_ZcUUR5WOhHWtEXZo8M3oEfdNg)
