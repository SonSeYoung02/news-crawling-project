import builtins
import unittest
from contextlib import ExitStack
from unittest.mock import Mock, patch
import main

class DirectContentTests(unittest.TestCase):
    def test_collection_requires_no_ai_and_preserves_foreign_text(self):
        article = {'url':'https://example.com/1','title':'Original English title','content':'Original full English body','source':'GeekNews','major_category':'AI'}
        save = Mock(return_value=True)
        original_import = builtins.__import__
        def no_ai(name, *args, **kwargs):
            if name.startswith(('llm','google.genai')): raise AssertionError('AI import forbidden')
            return original_import(name,*args,**kwargs)
        with ExitStack() as stack:
            for name, replacement in {'crawlers.get_all_articles':Mock(return_value=[article]),'db.init_db':Mock(), 'db.is_duplicate':Mock(return_value=False),'db.save_article':save}.items():
                stack.enter_context(patch(name,replacement))
            stack.enter_context(patch('builtins.__import__',side_effect=no_ai))
            main.run_pipeline()
        self.assertEqual(save.call_args.args[0], article)
        self.assertEqual(article['content'],'Original full English body')
    def test_every_source_saved_without_ai(self):
        articles = [{'url':f'https://example.com/{i}','source':source,'title':source,'content':'original body'} for i,source in enumerate(['GeekNews','GitHub Trending','Hugging Face','Reddit AI'])]
        with patch('crawlers.get_all_articles',return_value=articles),patch('db.init_db'),patch('db.is_duplicate',return_value=False),patch('db.save_article',return_value=True) as save:
            main.run_pipeline()
            self.assertEqual(save.call_count,4)
    def test_duplicate_refreshes_source_content(self):
        article={'url':'https://example.com','title':'Original','content':'Untranslated body','source':'GeekNews'}
        with patch('crawlers.get_all_articles',return_value=[article]),patch('db.init_db'),patch('db.is_duplicate',return_value=True),patch('db.refresh_article_from_source',return_value=True) as refresh,patch('db.save_article') as save:
            main.run_pipeline()
            refresh.assert_called_once_with(article)
            save.assert_not_called()

    def test_failed_fulltext_refresh_preserves_existing_body(self):
        import tempfile
        from pathlib import Path
        import db
        with tempfile.TemporaryDirectory() as folder, patch.object(db,'DB_PATH',Path(folder)/'news.db'):
            db.init_db()
            article={'url':'https://example.com','source':'Google News','title':'Title','content':'Existing complete original body'}
            db.save_article(article)
            db.refresh_article_from_source({**article,'content':'RSS fallback','content_is_fallback':True})
            self.assertEqual(db.get_article_by_url(article['url'])['content'],'Existing complete original body')

if __name__ == '__main__': unittest.main()
