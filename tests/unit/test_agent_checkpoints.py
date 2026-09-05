from luma.agents.checkpoints import psycopg_connection_url


def test_sqlalchemy_url_is_converted_for_langgraph_psycopg() -> None:
    assert (
        psycopg_connection_url("postgresql+psycopg://user:pass@db/luma")
        == "postgresql://user:pass@db/luma"
    )
