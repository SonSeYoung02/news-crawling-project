import unittest
from unittest.mock import patch
import main

class DirectContentTests(unittest.TestCase):
    def run_case(self, duplicate=False, translate=False):
        article = {'url':'https://example.com/a','title':'원래 제목','content':'문맥을 유지해야 하는 전체 본문입니다.','major_category':'AI','translate_to_korean':translate}
        with patch('crawlers.get_all_articles', return_value=[article]), \
             patch('db.init_db'), patch('db.is_duplicate', return_value=duplicate), \
             patch('db.update_content_if_empty'), patch('db.has_analysis', return_value=False), \
             patch('db.get_article_id_by_url', return_value=1), \
             patch('db.get_article_by_url', return_value=article), \
             patch('db.save_article', return_value=True) as save, \
             patch('db.save_analysis', return_value=True) as analysis, \
             patch('llm.analyzer.summarize', side_effect=AssertionError('AI 요약 호출 금지')), \
             patch('llm.analyzer.classify', return_value={'major_category':'AI','sub_category':'LLM','tags':[]}) as classify, \
             patch('llm.analyzer.translate_article_to_korean', return_value={'title':'번역 제목','content':'전체 번역 본문'}) as translation:
            main.run_pipeline()
            classify.assert_called_once()
            self.assertEqual(analysis.call_args.kwargs['summary'], '')
            if not duplicate:
                self.assertEqual(save.call_args.args[0]['content'], '전체 번역 본문' if translate else '문맥을 유지해야 하는 전체 본문입니다.')
            self.assertEqual(translation.call_count, int(translate and not duplicate))
    def test_new_article_no_summary(self): self.run_case()
    def test_duplicate_analysis_no_summary(self): self.run_case(duplicate=True)
    def test_translation_remains(self): self.run_case(translate=True)

if __name__ == '__main__': unittest.main()
