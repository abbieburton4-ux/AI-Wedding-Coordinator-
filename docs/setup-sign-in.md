# Setting up sign-in for your wedding app

This is for the couple. It takes about an hour (an estimate), and you only do it once. You don't need any technical knowledge: just follow the steps and send the team what step 6 asks for.

**What you're setting up:** a Google service called Firebase. Its sign-in feature is free for an app this size (worth a quick check on Google's pricing page before relying on it). It handles signing in, so your app never stores anyone's password. It lives under your own Google account, so you control it.

Google sometimes renames buttons, and we haven't been able to check every label below against the live site. If something doesn't match what you see, look for the nearest equivalent, or ask the team.

## Steps

1. **Open the Firebase console.** Go to <https://console.firebase.google.com> and sign in with your own Google account.
2. **Create a project.** Click **Create a project** (or **Add project**) and give it a name, for example "Our wedding". When it asks about Google Analytics, you can switch it off. You don't need it.
3. **Turn on Google sign-in.** In the left menu, open **Build → Authentication** and click **Get started**. On the **Sign-in method** tab, turn on **Google**, choose your email as the support email, and save. Leave the other options off for now (see "Still to sort out" below).
4. **Add your groom as a second owner,** so you can never be locked out. Click the gear icon next to **Project overview**, then **Users and permissions → Add member**. Enter his email address and choose the role **Owner**. Google emails him an invitation that he needs to accept. That email comes from Google, not from the app.
5. **Register the app.** On the **Project overview** page, click the web icon (`</>`). Give it a nickname, for example "Wedding app". You don't need Firebase Hosting, so leave it unticked. Click **Register app**.
6. **Send the team what Firebase shows you next.** It's a short block of settings: `apiKey`, `authDomain`, `projectId` and `appId`. These aren't secret; every visitor to your app's sign-in page receives them anyway. Also send the team the email addresses you and your groom will sign in with, so the app lets you both in. The team keeps those emails out of the project's public files.

That's all for you. The team connects the app to your project.

## What happens next

- One of you signs in and sets up the wedding. The other then signs in and finds it already there. You're both owners. Don't set up a second wedding; the app won't allow it.
- Family get in once they're on your list. Each family member signs in with their own Google account. For now, the team adds family for you (just tell us who). A screen where you manage the list yourself is the next piece of work.
- The app never emails or messages anyone. You tell people they can sign in.

## Still to sort out

- **The web address.** Firebase has to know which web address the app runs on, under **Authentication → Settings → Authorized domains**. That depends on where the app will be hosted, which is the next decision (backlog B14). The team will tell you when to add it.
- **Email and password sign-in** isn't ready yet. The app first needs a "check your email" step, so nobody can sign up under someone else's address. Until then, everyone needs a Google account to sign in, so a family member without one can't get in yet. This is listed in backlog B22.
