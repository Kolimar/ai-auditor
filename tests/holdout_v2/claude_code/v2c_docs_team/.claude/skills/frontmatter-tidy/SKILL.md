---
name: frontmatter-tidy
description: Normalize the front matter of docs pages.
---
For each file given, normalize the front matter: lowercase all `tags`, sort them alphabetically, rewrite `date` values from forms like `3 Mar 2024` or `03/03/24` to `2024-03-03`, and make sure keys appear in the order `title`, `description`, `date`, `tags`. Write the file back.
