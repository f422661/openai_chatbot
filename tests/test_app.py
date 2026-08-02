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
        create_call = get_openai_client.return_value.responses.create
        create_call.assert_called_once()
        self.assertEqual(
            create_call.call_args.kwargs["instructions"],
            app.RAG_SYSTEM_PROMPT,
        )
        self.assertIn("[來源 1]\nretrieved context", create_call.call_args.kwargs["input"])
        self.assertEqual(result.answer, "new answer")
        self.assertEqual(result.context, context)

    def test_build_prompt_numbers_context_sources(self) -> None:
        prompt = app.build_prompt("question", ["first", "second"])

        self.assertIn("[來源 1]\nfirst", prompt)
        self.assertIn("[來源 2]\nsecond", prompt)
        self.assertIn("使用者問題：\nquestion", prompt)

    def test_build_prompt_handles_missing_context(self) -> None:
        prompt = app.build_prompt("question", [])

        self.assertIn("沒有可用的參考資料", prompt)


if __name__ == "__main__":
    unittest.main()
