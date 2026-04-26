cat > stock_analyzer.py << 'EOF'
import os
import sys
import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from dotenv import load_dotenv

# 環境変数から API トークンを読み込む
load_dotenv()
API_TOKEN = os.getenv('JQUANTS_API_TOKEN', 'YOUR_API_TOKEN_HERE')

class StockAnalyzer:
    def __init__(self, api_token):
        """株式分析クラスの初期化"""
        try:
            from jquantsapi import Client
            self.client = Client(api_token)
            self.stocks_data = {}
            self.analysis_results = []
        except Exception as e:
            print(f"エラー: {e}")
            print("API トークンが正しく設定されているか確認してください")
            sys.exit(1)
    
    def fetch_all_stocks(self):
        """全銘柄情報を取得"""
        print("📊 全銘柄情報を取得中...")
        try:
            # 上場銘柄リストを取得
            list_data = self.client.get_lists()
            print(f"✅ {len(list_data)} 銘柄を取得しました")
            return list_data
        except Exception as e:
            print(f"❌ エラー: {e}")
            return []
    
    def fetch_stock_price(self, code):
        """個別銘柄の株価データを取得"""
        try:
            # 過去1年分のデータを取得
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=365)
            
            price_data = self.client.get_eq_bars_daily(
                code=code,
                from_yjm=start_date.strftime('%Y%m%d'),
                to_yjm=end_date.strftime('%Y%m%d')
            )
            return price_data
        except Exception as e:
            return None
    
    def calculate_indicators(self, prices):
        """テクニカル指標を計算"""
        if prices is None or len(prices) < 20:
            return None
        
        try:
            df = pd.DataFrame(prices)
            df['close'] = pd.to_numeric(df['close'], errors='coerce')
            df['volume'] = pd.to_numeric(df['volume'], errors='coerce')
            
            # 移動平均線
            df['ma_5'] = df['close'].rolling(window=5).mean()
            df['ma_20'] = df['close'].rolling(window=20).mean()
            df['ma_60'] = df['close'].rolling(window=60).mean()
            
            # RSI計算
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            df['rsi'] = 100 - (100 / (1 + rs))
            
            # MACD計算
            exp1 = df['close'].ewm(span=12, adjust=False).mean()
            exp2 = df['close'].ewm(span=26, adjust=False).mean()
            df['macd'] = exp1 - exp2
            df['signal'] = df['macd'].ewm(span=9, adjust=False).mean()
            
            return df
        except Exception as e:
            return None
    
    def calculate_score(self, code, stock_info, indicators):
        """独自スコアを計算（0-100点）"""
        score = 0
        details = {}
        
        try:
            if indicators is None or len(indicators) == 0:
                return 0, {}
            
            latest = indicators.iloc[-1]
            
            # 1. ゴールデンクロス判定 (20点)
            if latest['ma_5'] > latest['ma_20'] > latest['ma_60']:
                score += 20
                details['golden_cross'] = '✅ ゴールデンクロス'
            elif latest['ma_5'] < latest['ma_20'] < latest['ma_60']:
                score += 0
                details['golden_cross'] = '❌ デッドクロス'
            else:
                score += 10
                details['golden_cross'] = '🟡 中立'
            
            # 2. RSI判定 (20点)
            rsi = latest['rsi']
            if 30 <= rsi <= 60:
                score += 20
                details['rsi'] = f'✅ RSI適正: {rsi:.1f}'
            elif rsi < 30:
                score += 15
                details['rsi'] = f'🔼 RSI買われすぎ: {rsi:.1f}'
            else:
                score += 5
                details['rsi'] = f'🔽 RSI売られすぎ: {rsi:.1f}'
            
            # 3. MACD判定 (15点)
            if latest['macd'] > latest['signal']:
                score += 15
                details['macd'] = '✅ MACD上昇'
            else:
                score += 5
                details['macd'] = '🔽 MACD下降'
            
            # 4. 価格位置 (15点)
            if latest['close'] > latest['ma_20']:
                score += 15
                details['price_position'] = '✅ 価格 > MA20'
            else:
                score += 5
                details['price_position'] = '🔽 価格 < MA20'
            
            # 5. モメンタム (10点)
            momentum = (latest['close'] - indicators.iloc[-20]['close']) / indicators.iloc[-20]['close'] * 100
            if momentum > 2:
                score += 10
                details['momentum'] = f'✅ 上昇トレンド: {momentum:.1f}%'
            elif momentum > 0:
                score += 5
                details['momentum'] = f'🟡 微上昇: {momentum:.1f}%'
            else:
                score += 0
                details['momentum'] = f'🔽 下降: {momentum:.1f}%'
            
            # 6. 出来高 (10点)
            avg_volume = indicators['volume'].tail(20).mean()
            if latest['volume'] > avg_volume * 1.2:
                score += 10
                details['volume'] = '✅ 出来高増加'
            else:
                score += 5
                details['volume'] = '🟡 出来高通常'
            
            # 7. ボラティリティ (10点)
            volatility = indicators['close'].tail(20).std() / latest['close'] * 100
            if volatility < 3:
                score += 10
                details['volatility'] = f'✅ 安定: {volatility:.1f}%'
            elif volatility < 5:
                score += 7
                details['volatility'] = f'🟡 中程度: {volatility:.1f}%'
            else:
                score += 3
                details['volatility'] = f'⚠️ 高: {volatility:.1f}%'
            
            return min(score, 100), details
        
        except Exception as e:
            return 0, {}
    
    def analyze_all_stocks(self):
        """全銘柄を分析"""
        stocks = self.fetch_all_stocks()
        
        if not stocks:
            print("❌ 銘柄データを取得できませんでした")
            return
        
        print(f"\n🔍 {len(stocks)} 銘柄を分析中...\n")
        
        for idx, stock in enumerate(stocks[:50], 1):  # テスト用に最初の50銘柄
            code = stock.get('code')
            name = stock.get('name', '不明')
            price = stock.get('close_price', 0)
            
            print(f"[{idx}/{min(50, len(stocks))}] {code}: {name}", end=' ... ')
            
            try:
                # 株価データを取得
                price_data = self.fetch_stock_price(code)
                
                if price_data is None or len(price_data) == 0:
                    print("❌ データなし")
                    continue
                
                # テクニカル指標を計算
                indicators = self.calculate_indicators(price_data)
                
                if indicators is None:
                    print("❌ 分析失敗")
                    continue
                
                # スコアを計算
                score, details = self.calculate_score(code, stock, indicators)
                
                self.analysis_results.append({
                    'code': code,
                    'name': name,
                    'price': price,
                    'score': score,
                    'details': details
                })
                
                print(f"✅ スコア: {score}/100")
            
            except Exception as e:
                print(f"❌ エラー: {e}")
                continue
        
        # スコアでソート
        self.analysis_results.sort(key=lambda x: x['score'], reverse=True)
        print("\n✅ 分析完了")
    
    def display_results(self, top_n=50, min_price=None, max_price=None):
        """結果を表示"""
        if not self.analysis_results:
            print("❌ 分析結果がありません")
            return
        
        # 価格でフィルタ
        filtered = self.analysis_results
        if min_price is not None:
            filtered = [s for s in filtered if s['price'] >= min_price]
        if max_price is not None:
            filtered = [s for s in filtered if s['price'] <= max_price]
        
        print(f"\n{'='*80}")
        print(f"📈 株式分析結果 TOP {min(top_n, len(filtered))}")
        print(f"{'='*80}\n")
        
        for rank, stock in enumerate(filtered[:top_n], 1):
            print(f"【第{rank}位】")
            print(f"  銘柄コード: {stock['code']}")
            print(f"  銘柄名: {stock['name']}")
            print(f"  現在価格: ¥{stock['price']}")
            print(f"  スコア: {stock['score']}/100 {'🔥'*int(stock['score']/20)}")
            print(f"  分析詳細:")
            for key, value in stock['details'].items():
                print(f"    - {value}")
            print()
    
    def save_results_to_csv(self, filename='analysis_results.csv'):
        """結果をCSVに保存"""
        if not self.analysis_results:
            print("❌ 保存するデータがありません")
            return
        
        df = pd.DataFrame([{
            'code': s['code'],
            'name': s['name'],
            'price': s['price'],
            'score': s['score']
        } for s in self.analysis_results])
        
        df.to_csv(filename, index=False, encoding='utf-8-sig')
        print(f"✅ 結果を {filename} に保存しました")


def main():
    """メイン処理"""
    if API_TOKEN == 'YOUR_API_TOKEN_HERE':
        print("❌ エラー: API トークンが設定されていません")
        print("\n以下のいずれかを実行してください:")
        print("1. .env ファイルに JQUANTS_API_TOKEN を設定")
        print("2. 環境変数を設定: export JQUANTS_API_TOKEN='your_token'")
        print("3. stock_analyzer.py の API_TOKEN を直接編集")
        sys.exit(1)
    
    print("🚀 日本株分析プログラムを開始します\n")
    
    analyzer = StockAnalyzer(API_TOKEN)
    
    # 全銘柄を分析
    analyzer.analyze_all_stocks()
    
    # 結果を表示
    print("\n" + "="*80)
    print("📊 全銘柄ランキング")
    print("="*80)
    analyzer.display_results(top_n=50)
    
    # 価格帯別の結果表示
    print("\n" + "="*80)
    print("💰 低価格銘柄 (¥500以下)")
    print("="*80)
    analyzer.display_results(max_price=500, top_n=20)
    
    print("\n" + "="*80)
    print("💰 中価格銘柄 (¥1,000-¥3,000)")
    print("="*80)
    analyzer.display_results(min_price=1000, max_price=3000, top_n=20)
    
    print("\n" + "="*80)
    print("💰 高価格銘柄 (¥5,000以上)")
    print("="*80)
    analyzer.display_results(min_price=5000, top_n=20)
    
    # CSV に保存
    analyzer.save_results_to_csv()


if __name__ == '__main__':
    main()
EOF
