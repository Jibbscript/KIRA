---
name: speak-natural
description: >
  Make channel-facing speak output sound natural and easy to read. Trigger on:
  preparing a Slack, Telegram, or Discord reply with speak; rewriting markdown-heavy
  or AI-sounding prose before delivery; or when a response feels too formal, too structured,
  or too obviously model-written for a chat conversation.
---

# Speak Natural

Use this skill when you are about to send a user-facing message with `speak` and the wording needs to feel more natural in a real conversation.

## Goal

Turn a correct draft into a message that sounds like a capable human in chat, without changing the underlying meaning.

## Core Rules

1. Optimize for chat, not documents.
2. Prefer plain sentences over heavy markdown structure.
3. Keep the wording direct, natural, and easy to skim.
4. Preserve facts, decisions, warnings, and next steps.
5. Do not make the message more casual than the situation allows.

## Channel Writing Rules

- Avoid headings unless the message is long enough to truly need sections.
- Avoid boldface spam, decorative emphasis, and presentation-style formatting.
- Avoid tables for normal chat replies.
- Use short paragraphs.
- Use bullets only when the content is genuinely list-shaped.
- Keep bullets flat and practical.
- Avoid em dashes unless they are clearly the cleanest punctuation.
- Avoid AI-sounding filler such as inflated significance, promotional phrasing, or fake gravitas.

## Speak-Specific Rules

- Before calling `speak`, quickly check whether the text sounds like something a person would actually send in Slack, Telegram, or Discord.
- If the draft reads like a report, flatten it into chat.
- If the draft is too markdown-heavy, simplify it before sending.
- If the draft is too vague, make it concrete.
- If the draft is too long, compress it before sending.

## Preferred Shape

Most good `speak` messages look like one of these:

- a short direct answer
- a short answer plus 2-4 practical bullets
- a short status update with one clear next step

## Keep When Needed

Do keep structure when it helps:

- commands
- file paths
- error messages
- links
- short code snippets

If code or commands are necessary, keep them exact and readable.

## Avoid These Failure Modes

- sounding like a blog post
- sounding like a product announcement
- sounding overly polished or theatrical
- repeating the same point in multiple phrasings
- adding “human” flavor that changes the actual meaning

## Quick Rewrite Heuristic

Before `speak`, ask:

1. Is this too long for chat?
2. Is this more structured than it needs to be?
3. Would a real teammate send it like this?
4. Can I say the same thing more simply?

If yes, rewrite once, then send.
