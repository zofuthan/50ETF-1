#encoding=utf-8
import re
#import os
import scipy.stats as sc
import pandas as pd
import numpy as np
import datetime
import random
import datetime	
from QuantLib import *
import arch



#导入原始数据,进行数据处理 
#生成所需的sheet 以及sheet_names。
class dataProcess:
	def __init__(self):
		self.data()
	def data(self):
		print '开始导入数据'
		tempExcel=pd.read_excel('option.xlsx')
		print '数据导入完毕'
		num=tempExcel.columns.shape[0]
		underlying=tempExcel.iloc[:,-1:]
		new_underlying_index=pd.DatetimeIndex(underlying[8:].index)
		new_underlying_value=np.matrix(underlying[8:])
		spot_=pd.DataFrame(new_underlying_value,index=new_underlying_index,columns=['spot'])
		self.spot_=spot_		

		self.sheet=[]
		self.sheet_names=[]
		self.sheet_num=[]
		for i in range(2,num,4):
        		new_sheet=tempExcel.iloc[:,i-2:i]
        #sheet_names.append(new_sheet.columns[0])
        		new_index=pd.DatetimeIndex(new_sheet[8:].index)
        		new_value=np.matrix(new_sheet[8:])
        		temp=pd.DataFrame(new_value,index=new_index,columns=['mktprice','ptmtradeday'])
			temp['ptmtradeday'][temp['ptmtradeday']<2]=np.nan
			#print new_sheet.columns[0],pd.concat([temp,spot_],axis=1).dropna(axis=0).index,pd.concat([temp,spot_],axis=1)
			if len(pd.concat([temp,spot_],axis=1).dropna(axis=0).index)>=10:
        			min_=pd.concat([temp,spot_],axis=1).dropna(axis=0).index[0]
				max_=pd.concat([temp,spot_],axis=1).dropna(axis=0).index[-1]
				temp=pd.concat([temp,spot_],axis=1)[min_:max_].fillna(method='ffill')
			else:
				temp=pd.concat([temp,spot_],axis=1)[min_:max_].dropna()
        #交易数据小于10个交易日的，剔除。
        		if len(temp.index)>=10:
            			self.sheet.append(temp)
            			self.sheet_names.append(new_sheet.columns[0])
				self.sheet_num.append(new_sheet.iloc[0][0])
        		else:
            			pass
		self.code_index=pd.Series(self.sheet_num,index=self.sheet_names)
		rate_index=pd.read_excel('option.xlsx',sheetname='NoRiskRate')[2:].iloc[:,0]
		rate_index=pd.DatetimeIndex(rate_index.values)
		rate_values=pd.read_excel('option.xlsx',sheetname='NoRiskRate')[2:].iloc[:,1:3]
		self.rate=pd.DataFrame(np.matrix(rate_values),index=rate_index,columns=['shibor','10年期国债'])/100
#生成数据
class simulation:
    	def __init__(self,data,strike,option_type,preSpot_,contractUnit,costrate):
        	self.preSpot_=preSpot_
		self.cost_rate=costrate
        	self.option_type=option_type
        	self.data=data
		self.contractUnit=contractUnit
        	self.date_index=[]
        	for i in data.index:
        	        self.date_index.append((re.sub(r"\D","",str(i)[:10])))
        	self.strike=strike
        	self.mktprice=list(data['mktprice'])
        	self.mktprice_=pd.DataFrame(self.mktprice,index=data.index,columns=['mktprice'])
        	self.spot=list(data['spot'])
        	self.spot_=pd.DataFrame(self.spot,index=data.index,columns=['spot'])
        	self.ptmtradeday=list(data['ptmtradeday'])
        	self.ptmtradeday_=pd.DataFrame(self.ptmtradeday,index=data.index,columns=['ptmtradeday'])
        	self.impliedVolatility()
        	self.greeks()
        	#self.capital_account()
		#self.WW_capital_account()
        	#self.Zakamouline_capital_account()
		#self.WW_band(10)
        	#self.Zakamouline_band(10)
        	self.margin_account()
		self.ContractUnit()
    #求delta
    	def impliedVolatility(self):
        	self.implied=[]
        	i=0
        	u=SimpleQuote(self.strike)
        	r=SimpleQuote(0.03)
        	sigma=SimpleQuote(0)
        	for date in self.date_index:
            		year=int(date[:4])
            		month=int(date[4:6])
            		day=int(date[6:])
            		today=Date(day,month,year)
            		china_calendar=China()
            		period=Period(self.ptmtradeday[i]-1,Days)
            		exerciseday=china_calendar.advance(today,period)
            		#exerciseday=today+period
            		Settings.instance().evaluationDate=today
            		#r.setValue(self.r[i])
            		u.setValue(self.spot[i])
            		calloption=EuropeanOption(PlainVanillaPayoff(Option.Call,self.strike),EuropeanExercise(exerciseday))
            		putoption=EuropeanOption(PlainVanillaPayoff(Option.Put,self.strike),EuropeanExercise(exerciseday))
            		riskFreeCurve=FlatForward(0,TARGET(),QuoteHandle(r),Actual360())
            		volatility=BlackConstantVol(0,TARGET(),QuoteHandle(sigma),Actual360())
            		process=BlackScholesProcess(QuoteHandle(u),YieldTermStructureHandle(riskFreeCurve),BlackVolTermStructureHandle(volatility))
            		engine=AnalyticEuropeanEngine(process)
            		if self.option_type==1:
                		calloption.setPricingEngine(engine)
                		#当隐含波动率不存在时，令隐含波动率为0.0001，否则计算no-trade region会报错
                		if calloption.NPV()>=self.mktprice[i]:
                    			vol=0.0000
                    			#print 'call',date,'theoryvalue:',calloption.NPV(),'mktprice:',self.mktprice[i],self.spot[i]
                		else:
                    			vol=calloption.impliedVolatility(self.mktprice[i],process,1.0e-3,1000,0.0,50)
					
            		else:
                		putoption.setPricingEngine(engine)

                		if putoption.NPV()>self.mktprice[i]:
                    			vol=0.0000
                    			#print 'put',date,'theoryvalue:',putoption.NPV(),'mktprice',self.mktprice[i],self.spot[i]
                		else:
                    			vol=putoption.impliedVolatility(self.mktprice[i],process,1.0e-3,1000,0.0,50)
            		self.implied.append(vol)
            		i=i+1
        	self.implied_=pd.DataFrame(self.implied,index=self.data.index,columns=['implied'])
        
    
    	def greeks(self):
        	self.delta=[]
        	self.gamma=[]
        	self.vega=[]
		self.theta=[]
        	self.theoryvalue=[]
        	i=0
        	self.u=SimpleQuote(self.strike)
        	r=SimpleQuote(0.03)
        	self.sigma=SimpleQuote(0.2)
        	for date in self.date_index:
        	    	year=int(date[:4])
            		month=int(date[4:6])
            		day=int(date[6:])
            		today=Date(day,month,year)
            		china_calendar=China()
            		period=Period(self.ptmtradeday[i]-1,Days)
            		exerciseday=china_calendar.advance(today,period)
            		Settings.instance().evaluationDate=today
            		#r.setValue(self.r[i])
            		self.u.setValue(self.spot[i])
            		self.sigma.setValue(self.implied[i])
            		self.calloption=EuropeanOption(PlainVanillaPayoff(Option.Call,self.strike),EuropeanExercise(exerciseday))
            		self.putoption=EuropeanOption(PlainVanillaPayoff(Option.Put,self.strike),EuropeanExercise(exerciseday))
            		riskFreeCurve=FlatForward(0,TARGET(),QuoteHandle(r),Actual360())
            		volatility=BlackConstantVol(0,TARGET(),QuoteHandle(self.sigma),Actual360())
            		process=BlackScholesProcess(QuoteHandle(self.u),YieldTermStructureHandle(riskFreeCurve),BlackVolTermStructureHandle(volatility))
            		engine=AnalyticEuropeanEngine(process)
            		if self.option_type==1:
                		self.calloption.setPricingEngine(engine)
                		delta=self.calloption.delta()
                		gamma=self.calloption.gamma()
                		vega=self.calloption.vega()
				theta=self.calloption.theta()
                		theoryvalue=self.calloption.NPV()
            		else:
                		self.putoption.setPricingEngine(engine)
                		delta=self.putoption.delta()
                		gamma=self.putoption.gamma()
                		vega=self.putoption.vega()
				theta=self.putoption.theta()
                		theoryvalue=self.putoption.NPV()
            		self.delta.append(delta)
            		self.gamma.append(gamma)
            		self.vega.append(vega)
	    		self.theta.append(theta)
            		self.theoryvalue.append(theoryvalue)
            		i=i+1
        	self.delta_=pd.DataFrame(self.delta,index=self.data.index,columns=['delta'])
        	self.gamma_=pd.DataFrame(self.gamma,index=self.data.index,columns=['gamma'])
        	self.vega_=pd.DataFrame(self.vega,index=self.data.index,columns=['vega'])
		self.theta_=pd.DataFrame(self.theta,index=self.data.index,columns=['theta'])
        	self.theoryvalue_=pd.DataFrame(self.theoryvalue,index=self.data.index,columns=['theoryvalue'])
	
    
    #risk_aversion 为风险厌恶系数 \lambda_为交易成本
    	def WW_band(self,risk_aversion):
        	j=0
        	self.WWHedgeFreq=0
        	self.WWDeltaHold=[]
        	self.WW_band_sup=[]
        	self.WW_band_inf=[]
        	for i in self.data.index:
            		_ptmtradeday=self.ptmtradeday[j]-1
            		_lambda=self.cost_rate
            		_spot=self.spot[j]
            		_gamma=self.gamma[j]
            		r=0.03
            		H0=((3.0/2.0)*np.exp(-r*_ptmtradeday)*_lambda*_spot*(_gamma**2)/risk_aversion)**(1.0/3)
            		self.WW_band_sup.append(self.delta[j]+H0)
            		self.WW_band_inf.append(self.delta[j]-H0)
            		if j==0:
                		self.WWDeltaHold.append(self.delta[j])
            		else:
                		if self.WWDeltaHold[-1]<self.WW_band_sup[-1] and self.WWDeltaHold[-1]>self.WW_band_inf[-1]:
                    			self.WWDeltaHold.append(self.WWDeltaHold[-1])
                		elif self.WWDeltaHold[-1]<=self.WW_band_inf[-1]:
                    			self.WWDeltaHold.append(self.WW_band_inf[-1])
                    			self.WWHedgeFreq+=1
                		else:
                    			self.WWDeltaHold.append(self.WW_band_sup[-1])
                    			self.WWHedgeFreq+=1
            		j=j+1
        	self.WW_band_sup_=pd.DataFrame(self.WW_band_sup,index=self.data.index,columns=['WW_band_sup'])
        	self.WW_band_inf_=pd.DataFrame(self.WW_band_inf,index=self.data.index,columns=['WW_band_inf'])
        	self.WWDeltaHold_=pd.DataFrame(self.WWDeltaHold,index=self.data.index,columns=['WWDeltaHold'])
     
    	def Zakamouline_band(self,risk_aversion):
        	j=0
        	self.ZakamoulineHedgeFreq=0
        	self.Zakamouline_band_sup=[]
        	self.Zakamouline_band_inf=[]
        	self.Zakamouline_delta=[]
        	self.ZakamoulineDeltaHold=[]
        	r=0.03
        	for date in self.date_index:
            		_ptmtradeday=self.ptmtradeday[j]-1
            		_lambda=self.cost_rate
            		_spot=self.spot[j]
            		_gamma=self.gamma[j]
            		_sigma=self.implied[j]
            #print _sigma
            		year=int(date[:4])
            		month=int(date[4:6])
            		day=int(date[6:])
            		today=Date(day,month,year)
            		china_calendar=China()
            		period=Period(_ptmtradeday,Days)
            		exerciseday=china_calendar.advance(today,period)
            		Settings.instance().evaluationDate=today
            		#_ptmtradeday=float(_ptmtradeday)
            		H0=_lambda/(risk_aversion*_spot*(_sigma**2)*_ptmtradeday)
            		H1=1.12*(_lambda**0.31)*(_ptmtradeday**0.05)*((np.exp(-r*_ptmtradeday)/_sigma)**0.25)*((abs(_gamma)/risk_aversion)**0.5)
            		K=-4.76*((_lambda**0.78)/(_ptmtradeday**0.02))*((np.exp(-r*_ptmtradeday)/_sigma)**0.25)*((risk_aversion*(_spot**2)*abs(_gamma))**0.15)
            		#print K
            		modified_sigma=_sigma*np.sqrt(1-K)
            		#self.r.setValue(self.r[j])
            		self.u.setValue(self.spot[j])
            		self.sigma.setValue(modified_sigma)
            		#print modified_sigma
            
            		if self.option_type==1:
                		modified_delta=self.calloption.delta()
            		else:
                		modified_delta=self.putoption.delta()
            		self.Zakamouline_delta.append(modified_delta)
            		self.Zakamouline_band_sup.append(modified_delta+H1+H0)
            		self.Zakamouline_band_inf.append(modified_delta-H1-H0)
            		if j==0:
                		self.ZakamoulineDeltaHold.append(modified_delta)
            		else:
                		if self.ZakamoulineDeltaHold[-1]<self.Zakamouline_band_sup[-1] and self.ZakamoulineDeltaHold[-1]>self.Zakamouline_band_inf[-1]:
                    			self.ZakamoulineDeltaHold.append(self.ZakamoulineDeltaHold[-1])
                		elif self.ZakamoulineDeltaHold[-1]<=self.Zakamouline_band_inf[-1]:
                    			self.ZakamoulineDeltaHold.append(self.Zakamouline_band_inf[-1])
                    			self.ZakamoulineHedgeFreq=self.ZakamoulineHedgeFreq+1
                		else:
                    			self.ZakamoulineDeltaHold.append(self.Zakamouline_band_sup[-1])
                    			self.ZakamoulineHedgeFreq=self.ZakamoulineHedgeFreq+1
            		j=j+1
            
        	self.Zakamouline_delta_=pd.DataFrame(self.Zakamouline_delta,index=self.data.index,columns=['Zakamouline_delta'])
        	self.Zakamouline_band_sup_=pd.DataFrame(self.Zakamouline_band_sup,index=self.data.index,columns=['Zakamouline_band_sup'])
        	self.Zakamouline_band_inf_=pd.DataFrame(self.Zakamouline_band_inf,index=self.data.index,columns=['Zakamouline_band_inf'])
        	self.ZakamoulineDeltaHold_=pd.DataFrame(self.ZakamoulineDeltaHold,index=self.data.index,columns=['ZakamoulineDeltaHold'])
    
    #资金账户
    	def capital_account(self):
        	#self.cost_rate=0.0025
        	delta_diff_=self.delta_-self.delta_.shift(1)
        	capital_account=[a*b*self.contractUnit for a,b in zip(delta_diff_['delta'],self.spot_['spot'])]
        	capital_account_=pd.DataFrame(capital_account,index=self.data.index,columns=['capital_account'])
        	capital_account_cost=[]
        	for i in capital_account:
            		if i>0:
                		capital_account_cost.append(i*(1-self.cost_rate))
            		else:
                		capital_account_cost.append(i*(1+self.cost_rate))
        	self.capital_account_cost_=pd.DataFrame(capital_account_cost,index=self.data.index,columns=['capital_account'])
        	self.gross_return=self.capital_account_cost_.sum()
        	self.gross_cost=np.array(-self.capital_account_cost_.sum())+np.array(capital_account_.sum())
        
    	def WW_capital_account(self):
        #self.cost_rate=0.0025
        	delta_diff_=self.WWDeltaHold_-self.WWDeltaHold_.shift(1)
        	WW_capital_account=[a*b*self.contractUnit for a,b in zip(delta_diff_['WWDeltaHold'],self.spot_['spot'])]
        	WW_capital_account_=pd.DataFrame(WW_capital_account,index=self.data.index,columns=['WW_capital_account'])
        	WW_capital_account_cost=[]
        	for i in WW_capital_account:
            		if i>0:
                		WW_capital_account_cost.append(i*(1-self.cost_rate))
            		else:
                		WW_capital_account_cost.append(i*(1+self.cost_rate))
        	self.WW_capital_account_cost_=pd.DataFrame(WW_capital_account_cost,index=self.data.index,columns=['WW_capital_account'])
        	self.WW_gross_return=self.WW_capital_account_cost_.sum()
        	self.WW_gross_cost=np.array(-self.WW_capital_account_cost_.sum())+np.array(WW_capital_account_.sum())
        
    	def Zakamouline_capital_account(self):
        	#self.cost_rate=0.0025
        	delta_diff_=self.ZakamoulineDeltaHold_-self.ZakamoulineDeltaHold_.shift(1)
        	Zakamouline_capital_account=[a*b*self.contractUnit for a,b in zip(delta_diff_['ZakamoulineDeltaHold'],self.spot_['spot'])]
        	Zakamouline_capital_account_=pd.DataFrame(Zakamouline_capital_account,index=self.data.index,columns=['Zakamouline_capital_account'])
        	Zakamouline_capital_account_cost=[]
        	for i in Zakamouline_capital_account:
            		if i>0:
                		Zakamouline_capital_account_cost.append(i*(1-self.cost_rate))
            		else:
                		Zakamouline_capital_account_cost.append(i*(1+self.cost_rate))
        	self.Zakamouline_capital_account_cost_=pd.DataFrame(Zakamouline_capital_account_cost,index=self.data.index,columns=['Zakamouline_capital_account'])
        	self.Zakamouline_gross_return=self.Zakamouline_capital_account_cost_.sum()
        	self.Zakamouline_gross_cost=np.array(-self.Zakamouline_capital_account_cost_.sum())+np.array(Zakamouline_capital_account_.sum())
    
    #def option_account(self):
            
            
    	def margin_account(self):
        	self.margin_deposit=[]
        	self.initial_margin=[]
        	j=0
        	for i in  self.data.index:
            		_mktprice=self.mktprice[j]
            		_premktprice=self.mktprice_.shift(1).ix[j]['mktprice']
            		_spot=self.spot[j]
            		_preSpot=self.preSpot_.shift(1)['spot'][i]#50ETF前一天收盘价
            		if self.option_type==1:
                		call_out_option=max(self.strike-_preSpot,0)
                		self.margin_deposit.append((_mktprice+max(0.12*_spot-call_out_option,0.07*_preSpot))*self.contractUnit)
                		self.initial_margin.append((_premktprice+max(0.12*_spot-call_out_option,0.07*_preSpot))*self.contractUnit)
            		else:
                		put_out_option=max(_preSpot-self.strike,0)
                		self.margin_deposit.append((min(_mktprice+max(0.12*_spot-put_out_option,0.07*self.strike),self.strike))*self.contractUnit)
                		self.initial_margin.append((min(_premktprice+max(0.12*_spot-put_out_option,0.07*self.strike),self.strike))*self.contractUnit)
            		j=j+1
        	self.margin_deposit_=pd.DataFrame(self.margin_deposit,index=self.data.index,columns=['margin_deposit'])
        	self.initial_margin_=pd.DataFrame(self.initial_margin,index=self.data.index,columns=['initial_margin'])
	
	def ContractUnit(self):
		unit=[]
		partcipationday=datetime.datetime(2016,11,28)
		for i in self.data.index:
			if i<partcipationday:
				unit.append(10000)
			else:
				unit.append(self.contractUnit)
		self.unit_=pd.DataFrame(unit,index=self.data.index,columns=['contractunit'])
		
        
        
    
class sheetData:
	def __init__(self,costrate):
		self.costrate=costrate
		self.CreateSheet()
	def CreateSheet(self):
		delta_sheet=pd.DataFrame()
		gamma_sheet=pd.DataFrame()
		vega_sheet=pd.DataFrame()
		theta_sheet=pd.DataFrame()

		#WWBandInf_sheet=pd.DataFrame()
		#WWBandSup_sheet=pd.DataFrame()
		#WWDeltaHold_sheet=pd.DataFrame()

		#ZakamoulineBandInf_sheet=pd.DataFrame()
		#ZakamoulineBandSup_sheet=pd.DataFrame()
		#ZakamoulineDeltaHold_sheet=pd.DataFrame()
		#ZakamoulineDelta_sheet=pd.DataFrame()

		impliedVolatility_sheet=pd.DataFrame()
		theoryvalue_sheet=pd.DataFrame()
		mktprice_sheet=pd.DataFrame()
		ptmtradeday_sheet=pd.DataFrame()
		MarginAccount_sheet=pd.DataFrame()
		InitialAccount_sheet=pd.DataFrame()
		ContractUnit_sheet=pd.DataFrame()
		j=0
		self.dataprocess=dataProcess()
		option_startdate=[]
		self.per_option_startdate={}
		print '开始生成数据'
		for i in self.dataprocess.sheet:
			
			if self.dataprocess.sheet_names[j][-1]=='A':
				strike=self.dataprocess.sheet_names[j][-6:-1]
				contractUnit=10220
			else:
				strike=self.dataprocess.sheet_names[j][-4:]
				contractUnit=10000
			strike=float(strike)
			if self.dataprocess.sheet_names[j][5]==u'购':
				optiontype=1
			else:
				optiontype=0
			print self.dataprocess.sheet_names[j]
			print self.dataprocess.sheet_num[j]
			temp=simulation(self.dataprocess.sheet[j],strike,optiontype,self.dataprocess.spot_,contractUnit,self.costrate)
			option_startdate.append(str(temp.delta_.index[0])[:10])
			self.per_option_startdate[self.dataprocess.sheet_names[j]]=str(temp.delta_.index[0])[:10]

			delta_sheet=pd.concat([delta_sheet,temp.delta_],axis=1)
			gamma_sheet=pd.concat([gamma_sheet,temp.gamma_],axis=1)
			vega_sheet=pd.concat([vega_sheet,temp.vega_],axis=1)
			theta_sheet=pd.concat([theta_sheet,temp.theta_],axis=1)
			#WWBandInf_sheet=pd.concat([WWBandInf_sheet,temp.WW_band_inf_],axis=1)
			#WWBandSup_sheet=pd.concat([WWBandSup_sheet,temp.WW_band_sup_],axis=1)
			#WWDeltaHold_sheet=pd.concat([WWDeltaHold_sheet,temp.WWDeltaHold_],axis=1)
			MarginAccount_sheet=pd.concat([MarginAccount_sheet,temp.margin_deposit_],axis=1)
			InitialAccount_sheet=pd.concat([InitialAccount_sheet,temp.initial_margin_],axis=1)
			ContractUnit_sheet=pd.concat([ContractUnit_sheet,temp.unit_],axis=1)

			#ZakamoulineBandInf_sheet=pd.concat([ZakamoulineBandInf_sheet,temp.Zakamouline_band_inf_],axis=1)
			#ZakamoulineBandSup_sheet=pd.concat([ZakamoulineBandSup_sheet,temp.Zakamouline_band_sup_],axis=1)
			#ZakamoulineDeltaHold_sheet=pd.concat([ZakamoulineDeltaHold_sheet,temp.ZakamoulineDeltaHold_],axis=1)
			#ZakamoulineDelta_sheet=pd.concat([ZakamoulineDelta_sheet,temp.Zakamouline_delta_],axis=1)

			impliedVolatility_sheet=pd.concat([impliedVolatility_sheet,temp.implied_],axis=1)
			theoryvalue_sheet=pd.concat([theoryvalue_sheet,temp.theoryvalue_],axis=1)
			mktprice_sheet=pd.concat([mktprice_sheet,temp.mktprice_],axis=1)
			ptmtradeday_sheet=pd.concat([ptmtradeday_sheet,temp.ptmtradeday_],axis=1)
			j=j+1
		self.delta_sheet_=pd.DataFrame(np.matrix(delta_sheet),index=delta_sheet.index,columns=self.dataprocess.sheet_names)
		self.gamma_sheet_=pd.DataFrame(np.matrix(gamma_sheet),index=gamma_sheet.index,columns=self.dataprocess.sheet_names)
		self.vega_sheet_=pd.DataFrame(np.matrix(vega_sheet),index=vega_sheet.index,columns=self.dataprocess.sheet_names)
		self.theta_sheet_=pd.DataFrame(np.matrix(theta_sheet),index=theta_sheet.index,columns=self.dataprocess.sheet_names)
		
		#self.WWBandInf_sheet_=pd.DataFrame(np.matrix(WWBandInf_sheet),index=WWBandInf_sheet.index,columns=self.dataprocess.sheet_names)
		#self.WWBandSup_sheet_=pd.DataFrame(np.matrix(WWBandSup_sheet),index=WWBandSup_sheet.index,columns=self.dataprocess.sheet_names)
		#self.WWDeltaHold_sheet_=pd.DataFrame(np.matrix(WWDeltaHold_sheet),index=WWDeltaHold_sheet.index,columns=self.dataprocess.sheet_names)

		#self.ZakamoulineBandInf_sheet_=pd.DataFrame(np.matrix(ZakamoulineBandInf_sheet),index=ZakamoulineBandInf_sheet.index,columns=self.dataprocess.sheet_names)
		#self.ZakamoulineBandSup_sheet_=pd.DataFrame(np.matrix(ZakamoulineBandSup_sheet),index=ZakamoulineBandSup_sheet.index,columns=self.dataprocess.sheet_names)
		#self.ZakamoulineDeltaHold_sheet_=pd.DataFrame(np.matrix(ZakamoulineDeltaHold_sheet),index=ZakamoulineDeltaHold_sheet.index,columns=self.dataprocess.sheet_names)
		#self.ZakamoulineDelta_sheet_=pd.DataFrame(np.matrix(ZakamoulineDelta_sheet),index=ZakamoulineDelta_sheet.index,columns=self.dataprocess.sheet_names)		

		self.impliedVolatility_sheet_=pd.DataFrame(np.matrix(impliedVolatility_sheet),index=impliedVolatility_sheet.index,columns=self.dataprocess.sheet_names)
		self.theoryvalue_sheet_=pd.DataFrame(np.matrix(theoryvalue_sheet),index=theoryvalue_sheet.index,columns=self.dataprocess.sheet_names)
		self.mktprice_sheet_=pd.DataFrame(np.matrix(mktprice_sheet),index=mktprice_sheet.index,columns=self.dataprocess.sheet_names)
		self.ptmtradeday_sheet_=pd.DataFrame(np.matrix(ptmtradeday_sheet),index=ptmtradeday_sheet.index,columns=self.dataprocess.sheet_names)
		
		self.MarginAccount_sheet_=pd.DataFrame(np.matrix(MarginAccount_sheet),index=MarginAccount_sheet.index,columns=self.dataprocess.sheet_names)
		self.InitialAccount_sheet_=pd.DataFrame(np.matrix(InitialAccount_sheet),index=InitialAccount_sheet.index,columns=self.dataprocess.sheet_names)
		self.ContractUnit_sheet_=pd.DataFrame(np.matrix(ContractUnit_sheet),index=ContractUnit_sheet.index,columns=self.dataprocess.sheet_names)
		self.option_names=self.dataprocess.sheet_names
		self.option_startdate=set(option_startdate)
		temp=[]
		for i in self.option_startdate:
			temp.append(i)
		temp=pd.Series(temp)
		self.option_startdate=temp.sort_values()
		
		self.options_in_startdate={}
		for i in self.option_startdate:
			self.options_in_startdate[i]=[]
		for num,j in enumerate(option_startdate):
			self.options_in_startdate[j].append(self.option_names[num])
		
		print '数据生成完毕'
		

class realizedVolatility:
	def __init__(self):
		self.dataCreate()
		self.Forecast()
		self.factor()
		self.function()
		self.corr()
		self.forecast()
	def dataCreate(self):
		#sheet_temp=pd.read_excel('option.xlsx',sheetname='underlying')
		sheet_temp=pd.read_excel('temp.xlsx')
		index_temp=pd.DatetimeIndex(sheet_temp[8:].index)
		self.sheet_temp=pd.DataFrame(np.matrix(sheet_temp[8:]),index=index_temp,columns=['open','high','low','close','volume','total_turnover'])
		self.underlying=pd.DataFrame(np.matrix(self.sheet_temp.loc[:,'close']),columns=self.sheet_temp.index,index=['spot']).T
		self.underlyingYieldRate=np.log(self.underlying.pct_change(1)+1)
		self.underlyingYieldRate_5=np.log(self.underlying.pct_change(5)+1)
		self.underlyingYieldRate_10=np.log(self.underlying.pct_change(10)+1)
		self.underlyingYieldRate_20=np.log(self.underlying.pct_change(20)+1)
		self.underlyingYieldRate_30=np.log(self.underlying.pct_change(30)+1)
		self.underlyingYieldRate_60=np.log(self.underlying.pct_change(60)+1)
		
		self.realizedVol_90=self.underlyingYieldRate.rolling(window=90,center=False).std()*np.sqrt(252)
		self.realizedVol_60=self.underlyingYieldRate.rolling(window=60,center=False).std()*np.sqrt(252)
		self.realizedVol_30=self.underlyingYieldRate.rolling(window=30,center=False).std()*np.sqrt(252)
		self.realizedVol_20=self.underlyingYieldRate.rolling(window=20,center=False).std()*np.sqrt(252)
		self.realizedVol_10=self.underlyingYieldRate.rolling(window=10,center=False).std()*np.sqrt(252)

		self.realizedVol_day_90=self.underlyingYieldRate.rolling(window=90,center=False).std()
		self.realizedVol_day_60=self.underlyingYieldRate.rolling(window=60,center=False).std()
		self.realizedVol_day_30=self.underlyingYieldRate.rolling(window=30,center=False).std()
		self.realizedVol_day_20=self.underlyingYieldRate.rolling(window=20,center=False).std()
		self.realizedVol_day_10=self.underlyingYieldRate.rolling(window=10,center=False).std()
		temp=pd.concat([self.realizedVol_90,self.realizedVol_60,self.realizedVol_30,self.realizedVol_20,self.realizedVol_10],axis=1)
		self.realizedVol=pd.DataFrame(np.matrix(temp),index=temp.index,columns=['realizedVol_90','realizedVol_60','realizedVol_30','realizedVol_20','realizedVol_10'])
	def Forecast(self):
		vol_fore=[]
		test=self.underlyingYieldRate[30:]
		for i,j in enumerate(test.index):
    			train_=test.loc[:j].iloc[-30:]*100
    			am=arch.arch_model(train_)
    			res=am.fit()
    			vol_fore.append(res.params['omega']+res.params['alpha[1]']*np.mean(res.resid[-10:])**2+res.params['beta[1]']*np.mean(res.conditional_volatility[-10:])**2)
		self.VolForecast=0.01*np.sqrt(pd.DataFrame(vol_fore,index=test.index,columns=['vol_fore']))*np.sqrt(252)

	#因子指标计算
	def factor(self):
		self.P=pd.DataFrame(self.sheet_temp.loc[:,'open'],columns=['open'])
		self.H=pd.DataFrame(self.sheet_temp.loc[:,'high'],columns=['high'])
		self.L=pd.DataFrame(self.sheet_temp.loc[:,'low'],columns=['low'])
		self.C=pd.DataFrame(self.sheet_temp.loc[:,'close'],columns=['close'])
		self.V=pd.DataFrame(self.sheet_temp.loc[:,'volume'],columns=['volume'])
		self.TurnOver=pd.DataFrame(np.matrix(self.sheet_temp.loc[:,'total_turnover']),columns=self.sheet_temp.index,index=['TurnOver']).T
		self.yield_rate=self.C['close']/self.P['open']-1
		self.yield_rate=pd.DataFrame(np.matrix(self.yield_rate),index=['yield_rate'],columns=self.C.index).T
		
	
	def ADV_20(self,n):
		mean=pd.rolling_mean(self.V,n)
		ADV=self.V/mean
		return pd.DataFrame(ADV.values,index=ADV.index,columns=['ADV'])
	def TurnOver_20(self,n):
    		TurnOver_20=pd.rolling_mean(self.TurnOver,5)/pd.rolling_mean(self.TurnOver,n)
   	 	TurnOver_20=TurnOver_20
   	 	return pd.DataFrame(TurnOver_20.values,index=TurnOver_20.index,columns=['TurnOver']) 
	def RSI_20(self,n):
    		p=pd.DataFrame((self.C['close']-self.P['open'])/self.P['open'],index=self.C.index,columns=['yieldrate'])
    		p_max=pd.DataFrame(np.zeros(p.shape),index=p.index,columns=p.columns)
    		p_abs=p
    		for i in range(len(p)):
        		j=np.logical_and(p.ix[i]>0,p.ix[i]>0)
        		p_max.ix[i,j]=p.ix[i,j]
    		for i in range(len(p)):
        		j=np.logical_and(p.ix[i]<0,p.ix[i]<0)
        		p_abs.ix[i,j]=abs(p.ix[i,j])
    		RSI=pd.rolling_mean(p_max,n)/pd.rolling_mean(p_abs,n)*100
    		return pd.DataFrame(RSI.values,index=RSI.index,columns=['RSI'])
	def RE_20(self,n):
		return pd.DataFrame(self.C.pct_change(n).values,index=self.C.index,columns=['RE'])
	def VMC(self):
		return pd.DataFrame((self.TurnOver['TurnOver']/self.V['volume']-self.C['close']),columns=['VMC'])
	def LDECC_5(self):
    		p=pd.DataFrame((self.C['close']-self.P['open'])/self.P['open'],columns=['yieldrate'])
    		def rolling_5(A):#A为dataFrame 返回Series index=A.columns
        		return 1*A.iloc[-5]+2*A.iloc[-4]+3*A.iloc[-3]+4*A.iloc[-2]+5*A.iloc[-1]
    		MM=pd.DataFrame(rolling_5(p.iloc[-len(self.H)+1:-len(self.H)+6,:])).T
    		for i in range(6,len(self.H)-1):
        		MM=np.r_[MM,pd.DataFrame(rolling_5(p.iloc[(-len(self.H)+i-4):(-len(self.H)+i+1),:])).T]
    		MM=np.r_[MM,pd.DataFrame(rolling_5(p.iloc[-5:,:])).T]
    		return pd.DataFrame(MM,columns=['LDECC'],index=self.H.index[5:])
	def function(self):
		#self.func=pd.Series([self.ADV_20(20).dropna(),self.TurnOver_20(20).dropna(),self.RSI_20(20).dropna(),self.RE_20(20).dropna(),self.VMC().dropna(),self.LDECC_5().dropna()],index=['ADV','TurnOver','RSI','RE','VMC','LDECC'])
		self.func_name=['ADV_20(20)','ADV_20(15)','ADV_20(10)','ADV_20(5)','TurnOver_20(20)','TurnOver_20(15)','TurnOver_20(10)','RSI_20(20)','RSI_20(15)','RSI_20(10)','RSI_20(5)','RE_20(20)','RE_20(15)','RE_20(10)','RE_20(5)','VMC()','LDECC_5()']
		self.func=pd.Series([self.ADV_20(20).dropna(),self.ADV_20(15).dropna(),self.ADV_20(10).dropna(),self.ADV_20(5).dropna(),self.TurnOver_20(20).dropna(),self.TurnOver_20(15).dropna(),self.TurnOver_20(10).dropna(),self.RSI_20(20).dropna(),self.RSI_20(15).dropna(),self.RSI_20(10).dropna(),self.RSI_20(5).dropna(),self.RE_20(20).dropna(),self.RE_20(15).dropna(),self.RE_20(10).dropna(),self.RE_20(5).dropna(),self.VMC().dropna(),self.LDECC_5().dropna()],index=self.func_name)
	def corr(self):
		temp=pd.concat([self.underlyingYieldRate_5,self.ADV_20(20),self.ADV_20(15),self.ADV_20(10),self.ADV_20(5),self.TurnOver_20(20),self.TurnOver_20(15),self.TurnOver_20(10),self.RSI_20(20),self.RSI_20(15),self.RSI_20(10),self.RSI_20(5),self.RE_20(20),self.RE_20(15),self.RE_20(10),self.RE_20(5),self.VMC(),self.LDECC_5()],axis=1)
		temp=pd.DataFrame(np.matrix(temp),index=temp.index,columns=['underlyingYieldRate_5','ADV_20(20)','ADV_20(15)','ADV_20(10)','ADV_20(5)','TurnOver_20(20)','TurnOver_20(15)','TurnOver_20(10)','RSI_20(20)','RSI_20(15)','RSI_20(10)','RSI_20(5)','RE_20(20)','RE_20(15)','RE_20(10)','RE_20(5)','VMC()','LDECC_5()'])
		#temp=pd.concat([self.yield_rate,self.ADV_20(20),self.TurnOver_20(20),self.RSI_20(20),self.RE_20(20),self.VMC(),self.LDECC_5()],axis=1)
		ADV_20_corr=pd.rolling_corr(temp['underlyingYieldRate_5'],temp['ADV_20(20)'],10)
		ADV_15_corr=pd.rolling_corr(temp['underlyingYieldRate_5'],temp['ADV_20(15)'],10)
		ADV_10_corr=pd.rolling_corr(temp['underlyingYieldRate_5'],temp['ADV_20(10)'],10)
		ADV_5_corr=pd.rolling_corr(temp['underlyingYieldRate_5'],temp['ADV_20(5)'],10)
	
		TurnOver_20_corr=pd.rolling_corr(temp['underlyingYieldRate_5'],temp['TurnOver_20(20)'],10)
		TurnOver_15_corr=pd.rolling_corr(temp['underlyingYieldRate_5'],temp['TurnOver_20(15)'],10)
		TurnOver_10_corr=pd.rolling_corr(temp['underlyingYieldRate_5'],temp['TurnOver_20(10)'],10)

		RSI_20_corr=pd.rolling_corr(temp['underlyingYieldRate_5'],temp['RSI_20(20)'],10)
		RSI_15_corr=pd.rolling_corr(temp['underlyingYieldRate_5'],temp['RSI_20(15)'],10)
		RSI_10_corr=pd.rolling_corr(temp['underlyingYieldRate_5'],temp['RSI_20(10)'],10)
		RSI_5_corr=pd.rolling_corr(temp['underlyingYieldRate_5'],temp['RSI_20(5)'],10)

		RE_20_corr=pd.rolling_corr(temp['underlyingYieldRate_5'],temp['RE_20(20)'],10)
		RE_15_corr=pd.rolling_corr(temp['underlyingYieldRate_5'],temp['RE_20(15)'],10)
		RE_10_corr=pd.rolling_corr(temp['underlyingYieldRate_5'],temp['RE_20(10)'],10)
		RE_5_corr=pd.rolling_corr(temp['underlyingYieldRate_5'],temp['RE_20(5)'],10)

		VMC_corr=pd.rolling_corr(temp['underlyingYieldRate_5'],temp['VMC()'],10)
		LDECC_corr=pd.rolling_corr(temp['underlyingYieldRate_5'],temp['LDECC_5()'],10)
		corr=pd.concat([ADV_20_corr,ADV_15_corr,ADV_10_corr,ADV_5_corr,TurnOver_20_corr,TurnOver_15_corr,TurnOver_10_corr,RSI_20_corr,RSI_15_corr,RSI_10_corr,RSI_5_corr,RE_20_corr,RE_15_corr,RE_10_corr,RE_5_corr,VMC_corr,LDECC_corr],axis=1).dropna()
		self.corr=pd.DataFrame(np.matrix(corr),index=corr.index,columns=self.func_name)
	def unique(self,A):
    		D=[]
		temp1_2=[]
    		temp2=[]
    		for i in range(len(A)):
        		if A[i][:2]  not in temp1_2:
            			temp1_2.append(A[i][:2])
            			temp2.append(A[i])
    		return temp2
	def fore_(self,n,m):
		fore=[]
		for num,i in enumerate(self.corr.index[n:]):
			pp=[]
			temp_=self.unique(self.corr[n:].iloc[num].abs().sort_values(ascending=False).index)[:3]
			for j in temp_:
				pp.append(self.func[j].loc[:i].iloc[-n:])
			constant=np.ones(len(pp[0]))
			constant=pd.DataFrame(constant,index=pp[0].index,columns=['constant'])
			ppp=pd.concat([constant,pp[0],pp[1],pp[2]],axis=1)
			X=ppp.dropna()
			Y=self.underlyingYieldRate_5.loc[:i].iloc[-n:]
			temp1=np.array(X.T.dot(X).values,dtype='float')
			temp2=np.array(X.T.dot(Y).values,dtype='float')
			beta=np.linalg.inv(temp1).dot(temp2)
			X_=np.mean(X[-m:])
			Y_=X_.dot(beta)
			fore.append(Y_)
		fore=pd.DataFrame(fore,index=self.corr[n:].index,columns=['fore'])
		return fore
	def forecast(self):
		self.fore_30=self.fore_(30,10)
		self.fore_10=self.fore_(10,5)
		self.fore_5=self.fore_(5,3)
		
				
		

class winddata:
	def __init__(self):
		self.tempExcel=pd.read_excel('option.xlsx',sheetname='Greeks')
		self.realizedVoldata=pd.read_excel('vol.xlsx',sheetname='Sheet1')
		self.dataCreate()
	def dataCreate(self):
		new_index=pd.DatetimeIndex(self.realizedVoldata[8:].index)######
		start=new_index[0]
		end=new_index[-1]
		print 'winddata'
		self.tempExcel_=self.tempExcel[start:end]
		num=self.tempExcel_.columns.shape[0]
		self.wind_theoryValue_sheet=pd.DataFrame()
		self.wind_delta_sheet=pd.DataFrame()
		self.wind_gamma_sheet=pd.DataFrame()
		self.wind_vega_sheet=pd.DataFrame()
		self.wind_theta_sheet=pd.DataFrame()
		self.wind_impliedVolatility_sheet=pd.DataFrame()
		names=[]
		for i in range(0,num,8):
			names.append(self.tempExcel_.columns[i])
		for i in range(0,num,8):
    			theoryvalue=self.tempExcel_.iloc[:,i]
    			theoryvalue=pd.DataFrame(np.matrix(theoryvalue),columns=new_index,index=['theoryvalue']).T
    			self.wind_theoryValue_sheet=pd.concat([self.wind_theoryValue_sheet,theoryvalue],axis=1)
    
    			delta=self.tempExcel_.iloc[:,i+1]
    			delta=pd.DataFrame(np.matrix(delta),columns=new_index,index=['delta']).T
    			self.wind_delta_sheet=pd.concat([self.wind_delta_sheet,delta],axis=1)
		
			gamma=self.tempExcel_.iloc[:,i+2]
    			gamma=pd.DataFrame(np.matrix(gamma),columns=new_index,index=['gamma']).T
    			self.wind_gamma_sheet=pd.concat([self.wind_gamma_sheet,gamma],axis=1)
			
			vega=self.tempExcel_.iloc[:,i+3]
    			vega=pd.DataFrame(np.matrix(vega),columns=new_index,index=['vega']).T
    			self.wind_vega_sheet=pd.concat([self.wind_vega_sheet,vega],axis=1)
			
			theta=self.tempExcel_.iloc[:,i+4]
    			theta=pd.DataFrame(np.matrix(theta),columns=new_index,index=['theta']).T
    			self.wind_theta_sheet=pd.concat([self.wind_theta_sheet,theta],axis=1)

			impliedVolatility=self.tempExcel_.iloc[:,i+5]
    			impliedVolatility=pd.DataFrame(np.matrix(impliedVolatility),columns=new_index,index=['impliedVolatility']).T
    			self.wind_impliedVolatility_sheet=pd.concat([self.wind_impliedVolatility_sheet,impliedVolatility],axis=1)
		self.wind_theoryValue_sheet_=pd.DataFrame(np.matrix(self.wind_theoryValue_sheet),index=new_index,columns=names)
		self.wind_delta_sheet_=pd.DataFrame(np.matrix(self.wind_delta_sheet),index=new_index,columns=names)
		self.wind_gamma_sheet_=pd.DataFrame(np.matrix(self.wind_gamma_sheet),index=new_index,columns=names)
		self.wind_vega_sheet_=pd.DataFrame(np.matrix(self.wind_vega_sheet),index=new_index,columns=names)
		self.wind_theta_sheet_=pd.DataFrame(np.matrix(self.wind_theta_sheet),index=new_index,columns=names)
		self.wind_impliedVolatility_sheet_=pd.DataFrame(np.matrix(self.wind_impliedVolatility_sheet),index=new_index,columns=names)
		self.wind_realizedVol_30=pd.DataFrame(np.matrix(self.realizedVoldata[8:].iloc[:,0]),index=['wind_realizedVol_30'],columns=new_index).T/100
		self.wind_realizedVol_60=pd.DataFrame(np.matrix(self.realizedVoldata[8:].iloc[:,1]),index=['wind_realizedVol_60'],columns=new_index).T/100
		self.wind_realizedVol_90=pd.DataFrame(np.matrix(self.realizedVoldata[8:].iloc[:,2]),index=['wind_realizedVol_90'],columns=new_index).T/100


			




























