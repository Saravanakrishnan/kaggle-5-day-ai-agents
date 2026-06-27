#!/usr/bin/env node

import { Command } from 'commander';
import open from 'open';
import ora from 'ora';
import pc from 'picocolors';
import prompts from 'prompts';
import { getTopHeadlines, getTopicNews, getSearchNews, TOPICS, REGIONS } from './news.js';

// Setup Commander
const program = new Command();

program
  .name('google-news')
  .description('A command line tool to browse and search Google News')
  .version('1.0.0')
  .option('-s, --search <query>', 'search for news articles')
  .option('-t, --topic <topic>', 'browse news by topic (world, nation, business, technology, entertainment, sports, science, health)')
  .option('-l, --limit <count>', 'limit the number of articles displayed', parseInt, 10)
  .option('-r, --region <region_code>', 'set region code (US, GB, IN, CA, AU)', 'US')
  .option('-i, --interactive', 'run in interactive mode (default if no search/topic is specified)');

program.parse(process.argv);

const options = program.opts();

// Active configuration (can be updated in settings during session)
let currentRegion = options.region.toUpperCase();
if (!REGIONS[currentRegion]) {
  currentRegion = 'US';
}

/**
 * Helper to calculate relative time.
 */
function formatRelativeTime(date) {
  const now = new Date();
  const diffMs = now - date;
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffMins < 1) return 'just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  return `${diffDays}d ago`;
}

/**
 * Wrapper for prompt questions to handle Ctrl+C gracefully.
 */
async function safePrompt(question) {
  const response = await prompts(question, {
    onCancel: () => {
      console.log(pc.yellow('\nGoodbye!'));
      process.exit(0);
    }
  });
  return response;
}

/**
 * Print a nice ASCII banner for the CLI.
 */
function printBanner() {
  console.log('\n' + pc.cyan(pc.bold('==============================================')));
  console.log(pc.cyan(pc.bold('         📰 GOOGLE NEWS TERMINAL 📰           ')));
  console.log(pc.cyan(pc.bold('==============================================')));
  const currentRegionName = REGIONS[currentRegion]?.name || currentRegion;
  console.log(pc.dim(` Region: ${pc.yellow(currentRegionName)} | Time: ${new Date().toLocaleTimeString()}\n`));
}

/**
 * Renders list of articles to console (Direct/Static print mode).
 */
function renderStaticArticles(articles, limit) {
  const count = Math.min(articles.length, limit);
  if (count === 0) {
    console.log(pc.yellow('\nNo articles found.'));
    return;
  }

  console.log('\n' + pc.bold(pc.underline(`Latest Headlines (${count} items):`)) + '\n');
  for (let i = 0; i < count; i++) {
    const art = articles[i];
    const index = pc.magenta(`[${i + 1}]`);
    const timeStr = formatRelativeTime(art.pubDate);
    console.log(`${index} ${pc.bold(pc.cyan(art.title))}`);
    console.log(`    Source: ${pc.yellow(art.source)} • Published: ${pc.dim(timeStr)}`);
    console.log(`    Link: ${pc.dim(art.link)}\n`);
  }
}

/**
 * Interactive selector for article list.
 */
async function selectAndOpenArticle(articles, limit) {
  const count = Math.min(articles.length, limit);
  if (count === 0) {
    console.log(pc.yellow('\nNo articles found.'));
    await safePrompt({
      type: 'text',
      name: 'pressEnter',
      message: 'Press Enter to return to main menu...'
    });
    return;
  }

  const choices = articles.slice(0, count).map((art, idx) => {
    const relativeTime = formatRelativeTime(art.pubDate);
    // Constructing a structured preview text
    const label = `${pc.cyan(art.title)}\n     Source: ${pc.yellow(art.source)} • ${pc.dim(relativeTime)}`;
    return {
      title: label,
      value: art.link
    };
  });

  choices.push({ title: pc.red('⬅️  Back to Main Menu'), value: 'back' });

  const selectPrompt = await safePrompt({
    type: 'select',
    name: 'url',
    message: 'Use arrow keys to select an article to open in browser:',
    choices,
    // Setting page limit so long lists scroll nicely
    maxPerPage: 8
  });

  if (selectPrompt.url === 'back') {
    return;
  }

  const spinner = ora('Launching default browser...').start();
  try {
    await open(selectPrompt.url);
    spinner.succeed('Link opened in default web browser!');
  } catch (err) {
    spinner.fail(`Could not open browser: ${err.message}`);
  }

  const postAction = await safePrompt({
    type: 'select',
    name: 'action',
    message: 'What would you like to do now?',
    choices: [
      { title: '👁️  Return to this article list', value: 'list' },
      { title: '⬅️  Return to Main Menu', value: 'main' }
    ]
  });

  if (postAction.action === 'list') {
    await selectAndOpenArticle(articles, limit);
  }
}

/**
 * Topic selector menu.
 */
async function handleTopicSelection(limit) {
  const choices = Object.entries(TOPICS).map(([key, topic]) => ({
    title: topic.name,
    value: key
  }));
  choices.push({ title: pc.red('⬅️  Back to Main Menu'), value: 'back' });

  const response = await safePrompt({
    type: 'select',
    name: 'topic',
    message: 'Choose a news category:',
    choices
  });

  if (response.topic === 'back') {
    return;
  }

  const spinner = ora(`Fetching news for category: ${TOPICS[response.topic].name}...`).start();
  try {
    const articles = await getTopicNews(response.topic, currentRegion);
    spinner.succeed(`Fetched ${TOPICS[response.topic].name} news!`);
    await selectAndOpenArticle(articles, limit);
  } catch (err) {
    spinner.fail(`Failed to fetch topic: ${err.message}`);
    await safePrompt({
      type: 'text',
      name: 'pressEnter',
      message: 'Press Enter to return...'
    });
  }
}

/**
 * Search workflow prompt.
 */
async function handleSearch(limit) {
  const response = await safePrompt({
    type: 'text',
    name: 'query',
    message: 'Enter search keyword(s):',
    validate: val => val.trim().length > 0 ? true : 'Please enter a search term'
  });

  const spinner = ora(`Searching for "${response.query}"...`).start();
  try {
    const articles = await getSearchNews(response.query, currentRegion);
    spinner.succeed(`Search completed for "${response.query}"!`);
    await selectAndOpenArticle(articles, limit);
  } catch (err) {
    spinner.fail(`Failed to search news: ${err.message}`);
    await safePrompt({
      type: 'text',
      name: 'pressEnter',
      message: 'Press Enter to return...'
    });
  }
}

/**
 * Settings configuration menu.
 */
async function handleSettings() {
  const choices = Object.entries(REGIONS).map(([code, config]) => ({
    title: `${config.name} [${code}]`,
    value: code
  }));
  choices.push({ title: pc.red('⬅️  Back to Main Menu'), value: 'back' });

  const response = await safePrompt({
    type: 'select',
    name: 'region',
    message: `Select Region/Language (Current: ${currentRegion}):`,
    choices
  });

  if (response.region !== 'back') {
    currentRegion = response.region;
    console.log(pc.green(`\nSettings updated! Current region is now set to ${REGIONS[currentRegion].name}.`));
    await new Promise(resolve => setTimeout(resolve, 1500));
  }
}

/**
 * Main Interactive Loop.
 */
async function runInteractive(limit) {
  while (true) {
    printBanner();

    const response = await safePrompt({
      type: 'select',
      name: 'action',
      message: 'What would you like to read today?',
      choices: [
        { title: '🌟 Top Headlines', value: 'headlines' },
        { title: '🔍 Search News Articles', value: 'search' },
        { title: '📂 Browse by Topic', value: 'topics' },
        { title: '⚙️  Change Region/Language settings', value: 'settings' },
        { title: pc.red('❌ Exit'), value: 'exit' }
      ]
    });

    if (response.action === 'exit') {
      console.log(pc.yellow('\nGoodbye! Have a great day.'));
      process.exit(0);
    }

    if (response.action === 'headlines') {
      const spinner = ora('Fetching top headlines...').start();
      try {
        const articles = await getTopHeadlines(currentRegion);
        spinner.succeed('Fetched top headlines!');
        await selectAndOpenArticle(articles, limit);
      } catch (err) {
        spinner.fail(`Failed to fetch headlines: ${err.message}`);
        await safePrompt({
          type: 'text',
          name: 'pressEnter',
          message: 'Press Enter to return...'
        });
      }
    } else if (response.action === 'search') {
      await handleSearch(limit);
    } else if (response.action === 'topics') {
      await handleTopicSelection(limit);
    } else if (response.action === 'settings') {
      await handleSettings();
    }
  }
}

/**
 * Main Executable function.
 */
async function main() {
  const limit = options.limit;

  // Direct Mode execution (non-interactive if search or topic options are set)
  if (options.search || options.topic) {
    const spinner = ora('Fetching Google News...').start();
    try {
      let articles;
      if (options.search) {
        articles = await getSearchNews(options.search, currentRegion);
        spinner.succeed(`News results for search: "${options.search}"`);
      } else {
        const topicName = options.topic.toLowerCase();
        articles = await getTopicNews(topicName, currentRegion);
        const dispName = TOPICS[topicName]?.name || options.topic;
        spinner.succeed(`News results for category: "${dispName}"`);
      }
      renderStaticArticles(articles, limit);
    } catch (err) {
      spinner.fail(`Failed to load news: ${err.message}`);
      process.exit(1);
    }
  } else {
    // Run Interactive mode
    await runInteractive(limit);
  }
}

main().catch(err => {
  console.error(pc.red(`Unhandled exception: ${err.message}`));
  process.exit(1);
});
