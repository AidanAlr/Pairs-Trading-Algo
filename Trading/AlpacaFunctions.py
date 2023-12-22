import sys
import time

import pandas as pd
from alpaca.trading import OrderSide, TimeInForce, PositionSide
from alpaca.trading.client import TradingClient
from alpaca.trading.stream import TradingStream
from alpaca.trading.requests import MarketOrderRequest

import os

from utils.MyTimer import timeit

os.environ['APCA_API_BASE_URL'] = 'https://paper-api.alpaca.markets'


def connect_to_trading_stream():
    try:
        return TradingStream('api-key', 'secret-key', paper=True)
    except Exception:
        print("Error getting trade stream")


class AlpacaClient:
    def __init__(self):
        self.connected = False
        self.client = self.connect_to_alpaca("PKNWSWFGL7X6F50PJ8UH", "1qpcAmhEmzxONh3Im0V6lzgqtVOX2xD3k7mViYLX", paper=True)
        self.positions = self.client.get_all_positions()
        self.in_position = bool(self.client.get_all_positions())
        self.positions_df = self.get_positions_df()
        self.trading_stream = connect_to_trading_stream()

    @timeit
    def connect_to_alpaca(self, api_key: str, api_secret: str, paper: bool) -> TradingClient:
        try:
            trading_client = TradingClient(api_key, api_secret, paper=paper)
            account = trading_client.get_account()

            print('Connected to ALPACA.')
            print(f'${account.buying_power} is available as buying power.')
            self.connected = True
            return trading_client

        except Exception:
            print("Issue connecting to ALPACA.")

    def enter_hedge_position(self, stock_1, stock_2, side, leverage, hr):
        if side == "buy":
            stock_1_side = OrderSide.BUY
            stock_2_side = OrderSide.SELL
        elif side == "sell":
            stock_1_side = OrderSide.SELL
            stock_2_side = OrderSide.BUY

        try:
            # Placing orders
            market_order = self.client.submit_order(
                order_data=MarketOrderRequest(
                    symbol=stock_1,
                    qty=1 * leverage,
                    side=stock_1_side,
                    time_in_force=TimeInForce.DAY
                ))
            print(stock_1 + ' ' + stock_1_side + 'order executed')

            # Placing Short Order using hedge ratio
            market_order_2 = self.client.submit_order(
                order_data=MarketOrderRequest(
                    symbol=stock_2,
                    qty=round(hr * leverage),
                    side=stock_2_side,
                    time_in_force=TimeInForce.DAY
                ))
            print(stock_2 + ' ' + stock_2_side + 'order executed')

        except Exception:
            print("Error entering hedge position")

    def get_positions_df(self):
        assets = pd.DataFrame()
        if self.in_position:
            for n in range(len(self.client.get_all_positions())):
                pos = dict(self.client.get_all_positions()[n])
                pos = pd.DataFrame.from_dict(pos, orient='index').T
                assets = pd.concat([assets, pos])

                # Changing columns from str to float type
                columns_to_convert = ['unrealized_pl', 'cost_basis', 'market_value',
                                      'avg_entry_price', 'qty', 'unrealized_plpc']
                for column in columns_to_convert:
                    assets[column] = assets[column].astype(float)

        return assets

    def print_positions(self):
        portfolio = self.client.get_all_positions()
        side_map = {PositionSide.SHORT: "Short",
                    PositionSide.LONG: "Long"}
        print("Current Positions:")
        for position in portfolio:
            print("{} {} shares of {} purchased for {} current unrealised profit_pc is {}%"
                  .format(side_map[position.side],
                          position.qty.replace("-", ""),
                          position.symbol,
                          abs(float(position.cost_basis)),
                          self.get_unrealised_profit_pc()))



    def get_unrealised_profit_pc(self):
        try:
            profit = 0
            cost_basis = 0

            portfolio = self.client.get_all_positions()
            for position in portfolio:
                profit += float(position.unrealized_pl)
                cost_basis += float(abs(float(position.cost_basis)))

            return round(((profit / cost_basis) * 100), 2)
        except Exception:
            return 0

    def take_profit(self, tp):
        if self.get_unrealised_profit_pc() > tp:
            print("Executing orders to take profit...")
            if self.close_all_positions():
                print("Took profit")

    def stop_loss(self, sl):
        sl = abs(sl) * -1
        if self.get_unrealised_profit_pc() < sl:
            print("Executing orders to stop loss")
            if self.close_all_positions():
                print("Stopped Loss")



    def close_all_positions(self):
        # If not able to submit a market order should submit a limit order at current price
        close_info = self.client.close_all_positions(cancel_orders=True)
        for order in close_info:
            order = order.body
            side_map = {OrderSide.BUY: "buy",
                        OrderSide.SELL: "sell"}
            print(f"Attempted to {side_map[order.side]} {order.qty} shares of {order.symbol}. {order.filled_qty} orders filled for "
                  f"{order.filled_avg_price}")
            if order.filled_qty == order.qty:
                return True
            else:
                return False

    def use_live_tp_sl(self, tp, sl):
        print("Take Profit:" + str(tp) + "%")
        print("Stop Loss:" + str(abs(sl) * -1) + "%")
        self.print_positions()
        count = 0
        while True:
            output = f'{count}_Current Profit: {self.get_unrealised_profit_pc()} %'
            sys.stdout.write("\n")
            self.stop_loss(sl)
            self.take_profit(tp)
            sys.stdout.write("\r" + output.ljust(50))  # Overwrite the line with padding
            time.sleep(1)
            sys.stdout.flush()
            count += 1
