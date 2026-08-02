import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import app


class AnswerQuestionTests(unittest.TestCase):
    @patch("app.set_semantic_cache")
    @patch("app.get_semantic_cache")
    @patch("app.embed_text")
    def test_cache_hit_reuses_cached_answer(
        self,
        embed_text: Mock,
        get_semantic_cache: Mock,
        set_semantic_cache: Mock,
    ) -> None:
        embedding = [0.1, 0.2]
        embed_text.return_value = embedding
        get_semantic_cache.return_value = {
            "answer": "cached answer",
            "context": ["cached context"],
        }

        result = app.answer_question("test question")

        embed_text.assert_called_once_with("test question")
        get_semantic_cache.assert_called_once_with("test question", embedding)
        set_semantic_cache.assert_not_called()
        self.assertEqual(result.answer, "cached answer")
        self.assertEqual(result.context, ["cached context"])

    @patch("app.get_openai_client")
    @patch("app.fetch_top_chunks")
    @patch("app.set_semantic_cache")
    @patch("app.get_semantic_cache")
    @patch("app.embed_text")
    def test_cache_miss_uses_one_embedding_for_retrieval_and_cache(
        self,
        embed_text: Mock,
        get_semantic_cache: Mock,
        set_semantic_cache: Mock,
        fetch_top_chunks: Mock,
        get_openai_client: Mock,
    ) -> None:
        embedding = [0.1, 0.2]
        context = ["retrieved context"]
        embed_text.return_value = embedding
        get_semantic_cache.return_value = None
        fetch_top_chunks.return_value = context
        get_openai_client.return_value.responses.create.return_value = SimpleNamespace(
            output_text="new answer"
        )

        result = app.answer_question("test question")

        embed_text.assert_called_once_with("test question")
        get_semantic_cache.assert_called_once_with("test question", embedding)
        fetch_top_chunks.assert_called_once_with(embedding, app.TOP_K)
        set_semantic_cache.assert_called_once_with(
            "test question",
            embedding,
            "new answer",
            context,
        )
        self.assertEqual(result.answer, "new answer")
        self.assertEqual(result.context, context)


if __name__ == "__main__":
    unittest.main()
