//+------------------------------------------------------------------+
//|                                     TK_Momentum_Markers.mq5       |
//|  Marks ONLY the trades of the live strategy TK-Momentum-5-8-short |
//|  on the current chart (intended: M6 XAUUSD).                      |
//|                                                                  |
//|  For each such trade it draws:                                   |
//|    - a cyan dot at the EXACT entry (price + time)                |
//|    - a cyan dot at the EXACT exit  (price + time)                |
//|    - a dotted cyan line connecting entry dot -> exit dot         |
//|                                                                  |
//|  Identification is by MAGIC (999999999) + SYMBOL ("XAUUSD").     |
//|  READ-ONLY: this indicator places NO orders and modifies NO      |
//|  positions. It only creates visual chart objects, and it cleans  |
//|  up its own objects on deinit.                                   |
//|                                                                  |
//|  SOURCE OF TRUTH for magic/symbol:                               |
//|    sentinel_engine/strategies/live_configs_20.py                 |
//|      CONFIG_TK_MOMENTUM: symbol="XAUUSD", tf="M6"                 |
//|      TK_MOMENTUM_MAGIC_BASE=999999998; live position magic=+1 =  |
//|      999999999 (reconciler ficha F1).                            |
//+------------------------------------------------------------------+
#property copyright "SENTINEL"
#property version   "1.00"
#property indicator_chart_window
#property indicator_plots 0          // draws only objects, no plot buffers

//--- Identification of TK-Momentum-5-8-short trades ----------------
#define TKM_MAGIC   999999999          // live position magic (ficha F1)
#define TKM_SYMBOL  "XAUUSD"           // strategy symbol
#define TKM_PREFIX  "TKM_"             // namespace for all our objects

//--- Visual style --------------------------------------------------
input color  InpColor       = clrAqua;   // marker colour (cyan)
input int    InpDotArrow    = 159;       // Wingdings filled dot code
input int    InpDotSize     = 2;         // arrow (dot) size
input int    InpLineWidth   = 1;         // connector line width
input int    InpRefreshSecs = 2;         // redraw period (seconds)
input int    InpHistoryDays = 30;        // how far back to scan closed deals

//+------------------------------------------------------------------+
//| Helper: delete every object we ever created (by prefix)          |
//+------------------------------------------------------------------+
void TKM_ClearAll()
{
   ObjectsDeleteAll(0, TKM_PREFIX, -1, -1);
}

//+------------------------------------------------------------------+
//| Helper: create (or update) a cyan dot arrow                      |
//+------------------------------------------------------------------+
void TKM_Dot(const string name, const datetime t, const double price)
{
   if(ObjectFind(0, name) < 0)
      ObjectCreate(0, name, OBJ_ARROW, 0, t, price);
   ObjectSetInteger(0, name, OBJPROP_TIME,  0, t);
   ObjectSetDouble (0, name, OBJPROP_PRICE, 0, price);
   ObjectSetInteger(0, name, OBJPROP_ARROWCODE, InpDotArrow);
   ObjectSetInteger(0, name, OBJPROP_ANCHOR, ANCHOR_CENTER);
   ObjectSetInteger(0, name, OBJPROP_COLOR, InpColor);
   ObjectSetInteger(0, name, OBJPROP_WIDTH, InpDotSize);
   ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, name, OBJPROP_SELECTED,   false);
   ObjectSetInteger(0, name, OBJPROP_BACK,       false);
   ObjectSetInteger(0, name, OBJPROP_HIDDEN,     true);   // keep out of object-list clutter
}

//+------------------------------------------------------------------+
//| Helper: create (or update) a dotted cyan connector line          |
//+------------------------------------------------------------------+
void TKM_Line(const string name,
              const datetime t1, const double p1,
              const datetime t2, const double p2)
{
   if(ObjectFind(0, name) < 0)
      ObjectCreate(0, name, OBJ_TREND, 0, t1, p1, t2, p2);
   ObjectSetInteger(0, name, OBJPROP_TIME,  0, t1);
   ObjectSetDouble (0, name, OBJPROP_PRICE, 0, p1);
   ObjectSetInteger(0, name, OBJPROP_TIME,  1, t2);
   ObjectSetDouble (0, name, OBJPROP_PRICE, 1, p2);
   ObjectSetInteger(0, name, OBJPROP_COLOR, InpColor);
   ObjectSetInteger(0, name, OBJPROP_STYLE, STYLE_DOT);
   ObjectSetInteger(0, name, OBJPROP_WIDTH, InpLineWidth);
   ObjectSetInteger(0, name, OBJPROP_RAY_RIGHT, false);   // segment only, no ray
   ObjectSetInteger(0, name, OBJPROP_RAY_LEFT,  false);
   ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, name, OBJPROP_SELECTED,   false);
   ObjectSetInteger(0, name, OBJPROP_BACK,       false);
   ObjectSetInteger(0, name, OBJPROP_HIDDEN,     true);
}

//+------------------------------------------------------------------+
//| Core: scan open positions + closed history, (re)draw markers     |
//+------------------------------------------------------------------+
void TKM_Refresh()
{
   //--- 1) CLOSED trades: walk deal history --------------------------
   // Build, per POSITION_ID, the entry (DEAL_ENTRY_IN) and exit
   // (DEAL_ENTRY_OUT) time+price, filtering magic==TKM_MAGIC and the
   // strategy symbol. A position may have several partial OUT deals;
   // we take the FIRST IN and the LAST OUT so the connector spans the
   // full life of the trade.
   datetime from = TimeCurrent() - (datetime)InpHistoryDays * 24 * 60 * 60;
   if(HistorySelect(from, TimeCurrent()))
   {
      int total = HistoryDealsTotal();
      for(int i = 0; i < total; i++)
      {
         ulong ticket = HistoryDealGetTicket(i);
         if(ticket == 0)
            continue;

         long   magic  = HistoryDealGetInteger(ticket, DEAL_MAGIC);
         string sym    = HistoryDealGetString (ticket, DEAL_SYMBOL);
         if(magic != TKM_MAGIC || sym != TKM_SYMBOL)
            continue;

         long   entry  = HistoryDealGetInteger(ticket, DEAL_ENTRY);
         long   posid  = HistoryDealGetInteger(ticket, DEAL_POSITION_ID);
         datetime dtime= (datetime)HistoryDealGetInteger(ticket, DEAL_TIME);
         double price  = HistoryDealGetDouble (ticket, DEAL_PRICE);
         if(price <= 0.0 || posid == 0)
            continue;

         string base = TKM_PREFIX + (string)posid;

         if(entry == DEAL_ENTRY_IN)
         {
            // first IN wins (history is chronological; only create once)
            if(ObjectFind(0, base + "_IN") < 0)
               TKM_Dot(base + "_IN", dtime, price);
         }
         else if(entry == DEAL_ENTRY_OUT || entry == DEAL_ENTRY_OUT_BY)
         {
            // last OUT wins -> always overwrite with the newest OUT
            TKM_Dot(base + "_OUT", dtime, price);

            // draw / refresh the connector if the IN dot already exists
            if(ObjectFind(0, base + "_IN") >= 0)
            {
               datetime t_in = (datetime)ObjectGetInteger(0, base + "_IN", OBJPROP_TIME, 0);
               double   p_in =           ObjectGetDouble (0, base + "_IN", OBJPROP_PRICE, 0);
               TKM_Line(base + "_LINE", t_in, p_in, dtime, price);
            }
         }
      }
   }

   //--- 2) OPEN position: entry dot only (no exit yet) ---------------
   int pos_total = PositionsTotal();
   for(int i = 0; i < pos_total; i++)
   {
      ulong pticket = PositionGetTicket(i);
      if(pticket == 0)
         continue;
      if(PositionGetInteger(POSITION_MAGIC) != TKM_MAGIC)
         continue;
      if(PositionGetString(POSITION_SYMBOL) != TKM_SYMBOL)
         continue;

      long     posid = (long)PositionGetInteger(POSITION_IDENTIFIER);
      datetime t_in  = (datetime)PositionGetInteger(POSITION_TIME);
      double   p_in  = PositionGetDouble(POSITION_PRICE_OPEN);
      string   base  = TKM_PREFIX + (string)posid;

      // Draw the entry dot (uses exact position open time+price).
      TKM_Dot(base + "_IN", t_in, p_in);
      // No exit dot / no connector while the position is still open.
   }

   ChartRedraw(0);
}

//+------------------------------------------------------------------+
//| OnInit                                                           |
//+------------------------------------------------------------------+
int OnInit()
{
   IndicatorSetString(INDICATOR_SHORTNAME, "TK-Momentum Markers");

   // Gentle guard: this indicator is only meaningful on the strategy
   // symbol. It still runs on any chart, but warns if attached wrong.
   if(_Symbol != TKM_SYMBOL)
      Print("TK_Momentum_Markers: attached to ", _Symbol,
            " but strategy symbol is ", TKM_SYMBOL,
            " -- markers use absolute time/price so they will not show ",
            "on this chart. Attach to a ", TKM_SYMBOL, " chart (M6).");

   TKM_Refresh();
   EventSetTimer(InpRefreshSecs > 0 ? InpRefreshSecs : 2);
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| OnTimer -- periodic redraw so new/updated trades appear live     |
//+------------------------------------------------------------------+
void OnTimer()
{
   TKM_Refresh();
}

//+------------------------------------------------------------------+
//| OnCalculate -- required for an indicator; also refresh on ticks  |
//+------------------------------------------------------------------+
int OnCalculate(const int rates_total,
                const int prev_calculated,
                const datetime &time[],
                const double &open[],
                const double &high[],
                const double &low[],
                const double &close[],
                const long &tick_volume[],
                const long &volume[],
                const int &spread[])
{
   // Refresh on the first calculation only here; OnTimer handles the
   // steady-state cadence (avoids heavy history rescans every tick).
   if(prev_calculated == 0)
      TKM_Refresh();
   return(rates_total);
}

//+------------------------------------------------------------------+
//| OnDeinit -- clean up ALL our objects                             |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   EventKillTimer();
   TKM_ClearAll();
   ChartRedraw(0);
}
//+------------------------------------------------------------------+
