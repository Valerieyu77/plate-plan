# Run the React app

`localhost` is your own computer, so everyone runs their own copy of the app. To make sure your copy matches everyone else's, always pull the latest code first.

## Start the app

From the repository root, run:

```sh
git switch master
git pull
cd Project/frontend
npm install
npm run dev
```

Then open the address Vite prints (usually http://localhost:5173).

- Run all of these every time you start working. `git pull` gets your teammates' latest changes, and `npm install` adds any new packages they introduced.
- If the app is already running, stop it with Ctrl+C first.
- The backend only accepts the frontend on port **5173 or 3000**. If Vite picks another port because 5173 is busy, run `npm run dev -- --port 3000` instead.
- The app needs the backend running too (see "Getting started" in the README). To use another backend, copy `.env.example` to `.env.local` and change `VITE_API_URL`.

### Coming from the old `Frontend/` folder

The app used to live in `Frontend/my-react-app`. After pulling, an old `Frontend/` folder may still be there because git leaves untracked files behind (`node_modules`, `dist`, `.env.local`). Move your `.env.local` to `Project/frontend/` if you have one, then delete `Frontend/`. If you have a branch with frontend changes, run `git merge master` on it: git follows the renames, so your edits land in the new folder.

## Share your changes

Your edits show up right away on your own localhost, but teammates only see them after they are merged into `master`:

1. Create a branch: `git switch -c your-branch-name`
2. Commit and push:
   ```sh
   git add -A
   git commit -m "Describe your change"
   git push -u origin your-branch-name
   ```
3. Open a pull request on GitHub and merge it into `master`.

Teammates get your changes the next time they follow the steps in "Start the app." To bring the latest `master` into your own branch while you work, run `git pull origin master`.

## Live site

https://plate-plan-group6.vercel.app shows the most recently deployed version. It does not update when you push. The owner of the Vercel project redeploys it by running `npx vercel deploy --prod` from `Project/frontend`.

The live site talks to the backend at https://fa26-group6.onrender.com. That address is set as `VITE_API_URL` in the Vercel project settings, and it is baked in at build time, so changing it needs a redeploy. The Vercel project's Root Directory must be `Project/frontend` (or empty when deploying from that folder with the CLI).

## Production build

To create a production build, run `npm run build` from `Project/frontend`.
