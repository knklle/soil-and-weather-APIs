# Dashboard UI

`dashboard.py` contains the header, sidebar settings, result tabs, charts layout,
and downloads. Edit this file to change the presentation.

`streamlit_app.py` contains API configuration, requests, parsing, calculations,
chart definitions, and the integration workflow. Completed datasets are kept in
Streamlit session state so interacting with the UI does not rerun API requests.

Run from the project root:

```sh
.venv/bin/streamlit run streamlit_app.py
```

Colors and layout accents are in `styles.css`. Native widget colors are in
`../.streamlit/config.toml`. Chart palettes are in `streamlit_app.py` (`COLORS`)
and `dashboard.py` (`plot`). Restart Streamlit after changing its theme config.
