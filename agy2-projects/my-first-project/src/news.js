import Parser from 'rss-parser';

// Predefined topic mappings for Google News
export const TOPICS = {
  world: { name: 'World', key: 'WORLD' },
  nation: { name: 'Nation', key: 'NATION' },
  business: { name: 'Business', key: 'BUSINESS' },
  technology: { name: 'Technology', key: 'TECHNOLOGY' },
  entertainment: { name: 'Entertainment', key: 'ENTERTAINMENT' },
  sports: { name: 'Sports', key: 'SPORTS' },
  science: { name: 'Science', key: 'SCIENCE' },
  health: { name: 'Health', key: 'HEALTH' }
};

// Supported regions / language configurations
export const REGIONS = {
  US: { name: 'United States (English)', hl: 'en-US', gl: 'US', ceid: 'US:en' },
  GB: { name: 'United Kingdom (English)', hl: 'en-GB', gl: 'GB', ceid: 'GB:en' },
  IN: { name: 'India (English)', hl: 'en-IN', gl: 'IN', ceid: 'IN:en' },
  CA: { name: 'Canada (English)', hl: 'en-CA', gl: 'CA', ceid: 'CA:en' },
  AU: { name: 'Australia (English)', hl: 'en-AU', gl: 'AU', ceid: 'AU:en' }
};

const parser = new Parser({
  customFields: {
    item: [['source', 'source']],
  }
});

/**
 * Normalizes an RSS feed item into a structured format.
 * Google News titles are typically in the format: "Article Title - Source Name"
 */
function normalizeItem(item) {
  let title = item.title || 'No Title';
  let source = '';

  // Google News stores the source name in item.source as an object: { _: 'Source Name', $: { url: '...' } }
  if (item.source && typeof item.source === 'object') {
    source = item.source._ || '';
  } else if (typeof item.source === 'string') {
    source = item.source;
  }

  // Fallback: Parse the source from the title if not parsed by rss-parser
  if (!source) {
    const sourceMatch = title.match(/\s+-\s+([^-]+)$/);
    if (sourceMatch) {
      source = sourceMatch[1].trim();
      title = title.substring(0, sourceMatch.index).trim();
    }
  } else {
    // If we have source, strip it from the title to avoid redundancy
    const sourceSuffix = ` - ${source}`;
    if (title.endsWith(sourceSuffix)) {
      title = title.substring(0, title.length - sourceSuffix.length).trim();
    }
  }

  return {
    title,
    source: source || 'Google News',
    link: item.link,
    pubDate: item.pubDate ? new Date(item.pubDate) : new Date(),
    isoDate: item.isoDate
  };
}

/**
 * Builds the URL query parameters based on region settings.
 */
function getRegionParams(regionCode = 'US') {
  const config = REGIONS[regionCode.toUpperCase()] || REGIONS.US;
  return `hl=${config.hl}&gl=${config.gl}&ceid=${config.ceid}`;
}

/**
 * Fetches feed from url and parses it.
 */
async function fetchFeed(url) {
  try {
    const feed = await parser.parseURL(url);
    return feed.items.map(normalizeItem);
  } catch (error) {
    throw new Error(`Failed to fetch/parse news feed: ${error.message}`);
  }
}

/**
 * Fetches Top Headlines.
 */
export async function getTopHeadlines(region = 'US') {
  const params = getRegionParams(region);
  const url = `https://news.google.com/rss?${params}`;
  return fetchFeed(url);
}

/**
 * Fetches news by topic. Falls back to search if topic is not custom ID.
 */
export async function getTopicNews(topicKey, region = 'US') {
  const normalizedKey = topicKey.toLowerCase();
  const params = getRegionParams(region);
  
  if (TOPICS[normalizedKey]) {
    const topicKeyWord = TOPICS[normalizedKey].key;
    const url = `https://news.google.com/rss/headlines/section/topic/${topicKeyWord}?${params}`;
    return fetchFeed(url);
  }
  
  // Fallback to searching the term if topic key is not a predefined key
  return getSearchNews(topicKey, region);
}

/**
 * Searches for news.
 */
export async function getSearchNews(query, region = 'US') {
  const params = getRegionParams(region);
  const encodedQuery = encodeURIComponent(query);
  const url = `https://news.google.com/rss/search?q=${encodedQuery}&${params}`;
  return fetchFeed(url);
}
