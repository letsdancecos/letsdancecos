# Let's Dance Studios: Posting announcements

Announcements are shared publicly across the app. Only people who can edit this GitHub repository should publish them. Never enter student names, private details, addresses, payment information, or passwords.

## Publish one

1. Sign in to GitHub using a studio-authorized account.
2. Open the **letsdancecos/letsdancecos** repository, branch **main**.
3. Open **app/announcements.json** and choose the pencil icon (Edit this file).
4. Replace the empty list with announcement objects, keeping the JSON format below.
5. Choose **Commit changes** to main and allow GitHub Pages a minute or two to update.
6. Open https://letsdancecos.github.io/letsdancecos/app/ and check **Events**, then **Home** and **Parents**.

Example with ONE illustrative announcement (do not post this example as real news):

```json
{
  "events": [
    {
      "title": "Example recital reminder",
      "category": "recital",
      "date": "2026-11-01",
      "details": "Example only. Replace with confirmed studio details before publishing."
    }
  ]
}
```

- Categories must be **recital**, **closure**, or **news**.
- Dates use **YYYY-MM-DD**; use an empty string if no date is known.
- Title maximum: 90 characters. Details maximum: 400 characters.
- To post multiple announcements, separate objects with commas inside the `events` list.
- To take an announcement down, remove its object and commit the file.
- Edits reach everyone when they refresh or reopen the app. This is a shared noticeboard, **not** a push-notification system.
- GitHub Pages publication requires an internet connection. The app may show announcements unavailable when offline.

## Before launch

- Replace this manual editing workflow with a staff-only publisher if you want posting to be simple for nontechnical staff. Never put GitHub access tokens, email passwords, or student information into the publicly accessible app.
- Test publishing and deleting one real approved announcement from the authorized studio GitHub account.
- Check class schedule against https://www.letsdancecos.com/class-schedule, confirm phone/email/address, and test navigation on Android, iPhone, and desktop.
- Confirm the studio approves the announcements before posting.
