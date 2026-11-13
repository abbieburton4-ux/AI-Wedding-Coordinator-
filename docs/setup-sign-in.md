# Setting up sign-in for your wedding app

This is for the couple. It takes about an hour (an estimate), and you only do it once. You don't need any technical knowledge: just follow the steps and send the team what step 6 asks for.

**What you're setting up:** a Google service called Firebase. Its sign-in feature is free for an app this size (worth a quick check on Google's pricing page before relying on it). It handles signing in, so your app never stores anyone's password. It lives under your own Google account, so you control it.

Google sometimes renames buttons, and we haven't been able to check every label below against the live site. If something doesn't match what you see, look for the nearest equivalent, or ask the team.

## Steps

1. **Open the Firebase console.** Go to <https://console.firebase.google.com> and sign in with your own Google account.
2. **Create a project.** Click **Create a project** (or **Add project**) and give it a name, for example "Our wedding". When it asks about Google Analytics, you can switch it off. You don't need it.
3. **Turn on sign-in.** In the left menu, open **Build → Authentication** and click **Get started**. On the **Sign-in method** tab, turn on **Google**, choose your email as the support email, and save. Then click **Add new provider**, choose **Email/Password**, turn on the first switch (**Email/Password**), leave **Email link** off, and save. That second option is for family who don't have a Google account. Leave the other options off.

   **Then turn on email enumeration protection.** Still in **Authentication**, open the **Settings** tab and choose **User actions**. Make sure **Email enumeration protection (recommended)** is ticked, and click **Save** if you changed it. This stops a stranger from using the sign-in page to find out whether an email address has an account. Newer projects usually have it ticked already, but it's worth checking. Signing in works as before, except that a wrong email address and a wrong password now get the same error message.
4. **Add your groom as a second owner,** so you can never be locked out. Click the gear icon next to **Project overview**, then **Users and permissions → Add member**. Enter his email address and choose the role **Owner**. Google emails him an invitation that he needs to accept. That email comes from Google, not from the app.
5. **Register the app.** On the **Project overview** page, click the web icon (`</>`). Give it a nickname, for example "Wedding app". You don't need Firebase Hosting, so leave it unticked. Click **Register app**.
6. **Send the team what Firebase shows you next.** It's a short block of settings: `apiKey`, `authDomain`, `projectId` and `appId`. These aren't secret; every visitor to your app's sign-in page receives them anyway. Also send the team the email addresses you and your groom will sign in with, so the app lets you both in. The team keeps those emails out of the project's public files.

That's all for you. The team connects the app to your project.

## What happens next

- One of you signs in and sets up the wedding. The other then signs in and finds it already there. You're both owners. Don't set up a second wedding; the app won't allow it.
- **You manage who gets in.** Open your profile picture (top right), or the side menu on a computer, and choose **Who has access**. Add someone's email address and choose **Can edit** or **View only**. You can change that later, or remove them. Either of you can do this. At least one of you always keeps the power to manage access, so you can't lock yourselves out.
- **Adding someone doesn't send them anything.** Tell them yourself that they can sign in, and which email address you added.
- **Family sign in with Google, or with an email and password.** Someone without a Google account clicks **Create account**, enters the email you added and picks a password. The app then asks them to confirm their email: when they press **Send me a confirmation email**, Google's sign-in service sends them one email with a link. They open it, come back, and press **I've confirmed it, continue**. That email goes only when they ask for it. The app itself never emails or messages anyone.

## Still to sort out

- **The web address.** Firebase has to know which web address the app runs on, under **Authentication → Settings → Authorized domains**. That depends on where the app will be hosted, which is the next decision (backlog B14). The team will tell you when to add it.
