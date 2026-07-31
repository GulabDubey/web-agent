class SchemaLoader:

    @staticmethod
    def load():

        return """
users
------
id
name
email
mobile_no

blogs
------
id
user_id
add_date
title
sef_url
content
ai_summary
author
author_id
on_home_screen
image
category_id
blogimage
blog_faqs
is_news
is_case_study
created_at
created_by
updated_at
updated_by
is_deleted
"""