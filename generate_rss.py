#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator
from datetime import datetime, timezone
import os
import re
import urllib3

# SSL警告を無視する
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def fetch_articles():
    """
    Grant Thornton Japanのインサイトページから記事データを取得する
    """
    url = "https://www.grantthornton.jp/insight/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=30, verify=False)
        response.raise_for_status()
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, "html.parser")
        print(f"ページの取得に成功しました (ステータスコード: {response.status_code})")
    except Exception as e:
        print(f"ページの取得に失敗しました: {e}")
        return []

    articles = []
    
    # すべての article-tile 要素を取得
    article_tiles = soup.find_all("div", class_="article-tile")
    print(f"見つかった記事タイル数: {len(article_tiles)}")
    
    for tile in article_tiles:
        try:
            article = extract_article_data(tile)
            if article:
                articles.append(article)
                # 最初の5件だけ詳細を表示
                if len(articles) <= 5:
                    print(f"  ✓ 記事抽出: {article.get('title', '')[:50]}...")
        except Exception as e:
            print(f"記事の解析中にエラーが発生しました: {e}")
            continue
    
    return articles

def extract_article_data(tile):
    """
    個別の記事データを抽出する
    """
    article = {}
    
    # 1. data-anchor属性からリンクを取得（最も確実）
    link = tile.get("data-anchor")
    if link:
        if not link.startswith("http"):
            link = "https://www.grantthornton.jp" + link
        article["link"] = link
    
    # 2. タイトルの抽出（複数のパターン）
    title = None
    
    # パターン1: aタグのtitle属性
    title_elem = tile.find("a", class_="title")
    if title_elem:
        title = title_elem.get_text(strip=True)
        # リンクがまだない場合
        if not article.get("link") and title_elem.get("href"):
            link = title_elem.get("href")
            if not link.startswith("http"):
                link = "https://www.grantthornton.jp" + link
            article["link"] = link
    
    # パターン2: h2, h3, h4タグ
    if not title:
        for tag in ["h2", "h3", "h4"]:
            elem = tile.find(tag)
            if elem:
                title = elem.get_text(strip=True)
                # 親要素からaタグを探す
                parent_a = elem.find_parent("a")
                if parent_a and parent_a.get("href"):
                    link = parent_a.get("href")
                    if not link.startswith("http"):
                        link = "https://www.grantthornton.jp" + link
                    article["link"] = link
                break
    
    # パターン3: 任意のaタグ
    if not title:
        a_elem = tile.find("a", href=True)
        if a_elem:
            title = a_elem.get_text(strip=True)
            if not article.get("link") and a_elem.get("href"):
                link = a_elem.get("href")
                if not link.startswith("http"):
                    link = "https://www.grantthornton.jp" + link
                article["link"] = link
    
    if title:
        article["title"] = title
    
    # 3. カテゴリーの抽出
    category = None
    category_elem = tile.find("span", class_="category")
    if category_elem:
        category = category_elem.get_text(strip=True)
    else:
        # 他のパターンも試す
        cat_elem = tile.find("span", class_="article-tile__content-tagLink")
        if cat_elem:
            category = cat_elem.get_text(strip=True)
    
    if category:
        article["category"] = category
    
    # 4. 説明文の抽出
    description = None
    desc_elem = tile.find("p", class_="text")
    if desc_elem:
        description = desc_elem.get_text(strip=True)
    
    if description:
        article["description"] = description
    
    # 5. 日付の抽出
    date_elem = tile.find("span", class_="article-date")
    if date_elem:
        date_str = date_elem.get_text(strip=True)
        date_match = re.search(r'(\d{4})[/-](\d{1,2})[/-](\d{1,2})', date_str)
        if date_match:
            year, month, day = date_match.groups()
            article["pub_date"] = f"{year}-{int(month):02d}-{int(day):02d}"
    
    # 6. 画像の抽出
    img_elem = tile.find("img", class_="article-tile__image")
    if img_elem and img_elem.get("src"):
        img_src = img_elem.get("src")
        if not img_src.startswith("http"):
            img_src = "https://www.grantthornton.jp" + img_src
        article["image"] = img_src
    
    # タイトルとリンクが必須
    if article.get("title") and article.get("link"):
        return article
    
    # デバッグ情報
    print(f"  ✗ 記事抽出失敗: title={article.get('title')}, link={article.get('link')}")
    return None

def generate_rss(articles, output_path="feed.xml"):
    """
    記事データからRSSフィードを生成する
    """
    if not articles:
        print("警告: 記事がありません。空のRSSフィードを生成します。")
    
    fg = FeedGenerator()
    
    # フィードの基本情報
    fg.title("Grant Thornton Japan - インサイト")
    fg.link(href="https://www.grantthornton.jp/insight/", rel="alternate")
    fg.description("税務・会計・監査に関わる最新のニュース")
    fg.language("ja")
    
    # 現在時刻をUTCで設定
    now = datetime.now(timezone.utc)
    fg.lastBuildDate(now)
    fg.pubDate(now)
    
    # 各記事を追加
    for article in articles:
        try:
            entry = fg.add_entry()
            entry.title(article.get("title", "無題"))
            entry.link(href=article.get("link", ""))
            entry.guid(article.get("link", ""), permalink=True)
            
            # 説明の設定
            description = article.get("description", "")
            category = article.get("category", "")
            
            if category:
                full_description = f"【{category}】\n{description}"
            else:
                full_description = description
            
            entry.description(full_description)
            
            if category:
                entry.category(term=category)
            
            # 公開日
            if article.get("pub_date"):
                try:
                    pub_date = datetime.strptime(article["pub_date"], "%Y-%m-%d")
                    pub_date = pub_date.replace(tzinfo=timezone.utc)
                    entry.pubDate(pub_date)
                except Exception as e:
                    print(f"日付設定エラー: {e}")
            
            # 画像
            if article.get("image"):
                entry.enclosure(article["image"], 0, "image/jpeg")
        except Exception as e:
            print(f"エントリ追加エラー: {e}")
            continue
    
    # RSSファイルを生成
    rss_str = fg.rss_str(pretty=True)
    
    with open(output_path, "wb") as f:
        f.write(rss_str)
    
    print(f"\nRSSフィードを生成しました: {output_path}")
    print(f"記事数: {len(articles)}")

def main():
    """
    メイン処理
    """
    print("Grant Thornton Japan インサイト RSS生成スクリプト")
    print("=" * 50)
    
    # 記事を取得
    articles = fetch_articles()
    
    # 結果を表示
    print(f"\n抽出結果: {len(articles)}件の記事を取得")
    
    if articles:
        print("\n最新の記事 (最大5件):")
        for i, article in enumerate(articles[:5], 1):
            title = article.get("title", "無題")[:60]
            if len(article.get("title", "")) > 60:
                title += "..."
            print(f"  {i}. {title}")
            print(f"     日付: {article.get('pub_date', '不明')}")
            print(f"     カテゴリー: {article.get('category', 'なし')}")
    else:
        print("\n[ステッカー] 記事が1件も見つかりませんでした。")
        print("  サイトの構造が変更されている可能性があります。")
    
    # RSSを生成
    generate_rss(articles, "feed.xml")

if __name__ == "__main__":
    main()
