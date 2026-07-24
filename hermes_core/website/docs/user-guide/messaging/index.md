---
sidebar_position: 1
title: "Messaging Gateway"
description: "Overview of the retained Telegram, WhatsApp, Email, DingTalk, Weixin, and QQBot adapters"
---

# Messaging Gateway

The gateway connects Hermes to the product's retained messaging adapters:

- Mainland China profile: Weixin, QQBot, and DingTalk.
- Southeast Asia profile: Telegram, WhatsApp, and Email.

Each adapter routes messages through the shared session store and agent loop.
The gateway also runs scheduled jobs and can deliver their results back to a
retained platform.

## Setup

Use the interactive setup command:

```bash
hermes gateway setup
```

The setup flow only exposes platforms available in the active product profile.
Unknown, removed, and plugin-provided platform names are ignored.

## Access control

The gateway denies users that are neither allowlisted nor approved through DM
pairing. Configure the retained adapter's allowlist, or explicitly opt into
open access:

```bash
GATEWAY_ALLOW_ALL_USERS=true
```

Open access is not recommended for an agent with terminal or file tools.

## Sessions and home channels

Sessions persist until reset. `/sethome` selects the current conversation as
the default target for reminders and cross-platform delivery. A delivery target
outside the active product profile is recorded as unsupported instead of being
rerouted.

## Platform guides

- [Telegram](telegram.md)
- [WhatsApp](whatsapp.md)
- [Email](email.md)
- [DingTalk](dingtalk.md)
- [Weixin](weixin.md)
- [QQBot](qqbot.md)
