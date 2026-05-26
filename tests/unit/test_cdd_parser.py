from tr_seo_contracts.module0 import CDDFileMeta
from tr_seo_module0.cdd_parser import CDDParser


def test_csv_cdd_parser_extracts_preview() -> None:
    parser = CDDParser()
    file_meta = CDDFileMeta(
        filename="client-cdd.csv",
        content_type="text/csv",
        size_bytes=32,
        extension=".csv",
    )

    result = parser.parse(file_meta, b"services,locations\nSEO,Sydney")

    assert result.parser_used == "csv"
    assert "services | locations" in result.text_preview
