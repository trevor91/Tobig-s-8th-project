import requests, re
from bs4 import BeautifulSoup
import datetime
import time
from urllib.parse import quote
import pymysql.cursors

class keyword:
	def __init__(self, myKeyword, startTime, endTime):
		self.myKeyword = myKeyword
		self.start = startTime
		self.end = endTime

		self.newsUrl = list()
		self.news = list()
		self.conn = 0
	
	def getKeyword(self):
		return(self.myKeyword)

	def getstartTime(self):
		return(self.start)

	def getendTime(self):
		return(self.end)

	def getNews(self):
		return(self.news)


	############################## crawling function ##############################
	def getUrl(self):
		mainURL = "https://search.naver.com/search.naver?where=news&ie=utf8&sm=tab_opt&sort=0&photo=0&field=0&reporter_article=&pd=3&docid=&nso=so%3Ar%2Cp%3Afrom{start2}to{end2}%2Ca%3Aall&mynews=0&mson=0&refresh_start=0&related=0&query={query}&ds={start}&de={end}"
		if(self.start==self.end):
			self.end = self.end[0:-1] + str((int(self.end[-1]) + 1))

		url = mainURL.format(\
			query = quote(self.myKeyword)\
			,start = self.start\
			,end = self.end\
			,start2 = re.sub('.','',self.start)\
			,end2 = re.sub('.','',self.end))
		return(url)

	def getNextPage(self, soup):
		try:
			cont = soup.select('#main_pack > div.paging > a.next')
			for href in cont:
				return(href.get('href'))
		except:
			return(None)


	def getSingleNewsUrl(self, soup):
		rst = list()
		try:			
			cont = soup.select('#main_pack > div.news.mynews.section > ul > li > dl > dd > a')
			for a in cont:
				rst.append(a.get('href'))
			return(rst)
		except Exception as e:
			return(None)


	# get new url list
	def getResource(self, url):
		rst = dict()
		response = requests.get(url)
		# status check
		if response.status_code == 200:
			html = response.text
			soup = BeautifulSoup(html, 'html.parser')
			
			rst['news'] = self.getSingleNewsUrl(soup)
			print(len(rst['news']))
			
			for single in rst['news']:
				self.insertNewsList(single)
			
			for news in rst['news']:
				self.newsUrl.append(news)
			
			rst["next"] = self.getNextPage(soup)
			return(rst["next"])

		# ERROR
		elif response.status_code == 403:
			print('getNextPage()\terr\t' + str(response.status_code) + '\n' + url)
			time.sleep(10)
			self.getResource(url)
			return(None)
		else:
			print('getNextPage()\terr\t' + str(response.status_code) + '\n' + url)
			return(None)


	# news crawling
	def form1(self, url, soup): #http://news.naver.com # no redirect
		rst = dict()
		rst['url'] = url
		# get title
		rst['title'] = soup.select('#articleTitle')[0].text
		# get date
		rst['date'] = soup.select('#main_content > div.article_header > div.article_info > div.sponsor > span.t11')[0].text
		# get company name
		rst['company'] = soup.select('#main_content > div.article_header > div.press_logo > a > img')[0].get('title')
		# get contents
		rst['cont'] = soup.select('#articleBodyContents')[0].text
		temp = "\n\n\n\n\n// flash 오류를 우회하기 위한 함수 추가\nfunction _flash_removeCallback() {}"
		if temp in rst['cont']:
			rst['cont'] = re.sub(temp, '', rst['cont'])

		return(rst)


	def form2(self, url, soup): # http://entertain.naver.com # redirect
		rst = dict()
		rst['url'] = url
		# get title
		rst['title'] = soup.select('#content > div.end_ct > div > h2')[0].text
		# get date
		rst['date'] = soup.select('#content > div.end_ct > div > div.article_info > span > em')[0].text
		if '오전' in rst['date']:
			rst['date'] = re.sub('오전','',rst['date'])
		if '오후' in rst['date']:
			temp = rst['date'].split('오후')
			temp2 = temp[1].split(':')
			t = int(temp2[0]) + 12
			if t > 23:
				t = 0
			rst['date'] = "%s %s:%s" % (temp[0], str(t), temp2[1])
		# get company name
		rst['company'] = soup.select('#content > div.end_ct > div > div.press_logo > a > img')[0].get('alt')
		# get contents
		rst['cont'] = soup.select('#articeBody')[0].text
		return(rst)


	def getNewsInfo(self, url):
		response = requests.get(url, allow_redirects=True)
		# print(response.history) # redirect check.
		print(response.url)
		html = response.text
		soup = BeautifulSoup(html, 'html.parser')

		if response.status_code == 200:
			#http://news.naver.com
			if 'http://news.naver.com' in response.url:
				news = self.form1(url, soup)
				
			# http://entertain.naver.com
			elif 'http://entertain.naver.com' in response.url:
				news = self.form2(url, soup)

			if self.conn != 0:
				self.insertNews(news)
			return(news)
		else:
			print("getNewsInfo ERROR\t" + str(response.status_code) + '\t' + url)
	
	def getNewsContCrawling(self, url): #url을 db에서 받아와서 컨텐츠 수집
		for news in url:
			print("news:\t" + news)
			self.news.append(self.getNewsInfo(news))

	def newsCrawling(self, newsList = True, newsCont = True):
		# step1. 해당조건의 뉴스기사 검색 URL 생성
		url = self.getUrl()
		if newsList:
			# step2. 뉴스 기사 검색을 통해서 기사 URL list 생성
			while 1:
				# URL check
				if(url[0:6] != "https:"):
					url = "https:" + url

				# get single new url & next page url. => return (next page)
				url = self.getResource(url)
				if(url == None):
					break

		if newsCont:
			for news in self.newsUrl:
				print("news:\t" + news)
				self.news.append(self.getNewsInfo(news))


	############################## search function ##############################
	def removeWhiteSpace(self, string):
		pattern = re.compile(r'\s+')
		return(re.sub(pattern, '', string))


	def searchKeyword(self, strings):
		newsTitle = list()
		newsCont = list()
		keywordList = list()

		rst = list()

		# 공백 제거 (제목, 내용)
		for oneNews in self.news:
			print(oneNews)
			try:
				newsTitle.append(self.removeWhiteSpace(oneNews['title']))
			except TypeError as e:
				newsTitle.append('empty')
			try:
				newsCont.append(self.removeWhiteSpace(oneNews['cont']))
			except TypeError as e:
				newsCont.append('empty')

		# 공백 제거 (string)
		for string in strings:
			keywordList.append(self.removeWhiteSpace(str(string)))


		# keywordList을 긴거 순으로 정렬
		keywordList.sort(key = len, reverse = True)

		# 검색

		# for idx, title in enumerate(newsTitle):
		# 	temp = dict()
		# 	for string in keywordList:
		# 		temp[string] = title.count(string)
		# 		newsTitle[idx] = re.sub(string, '', title)
		# 	rst.append(temp)

		for idx, cont in enumerate(newsCont):
			temp = dict()
			for string in keywordList:
				temp[string] = cont.count(string)
				if temp[string]:
					print(string, str(temp[string]))
				newsCont[idx] = re.sub(string, '', cont)
			print('-'*30)
			rst.append(temp)


		# for string in keywordList:
		# 	for idx, title in enumerate(newsTitle):
		# 		temp[string] = title.count(string)
		# 		# print('%s title count: %d' % (string, title.count(string)))
		# 		newsTitle[idx] = re.sub(string, '', title)
		# 	for idx, content in enumerate(newsCont):
		# 		temp[string] = content.count(string) + rst[string]
		# 		# print('%s content count: %d' % (string, content.count(string)))
		# 		newsCont[idx] = re.sub(string, '', content)

		return(rst)


	############################## SQL function ##############################
	def sqlConnect(self, host, user, pw):
		print("DB connect...")
		self.conn = pymysql.connect(host=host,user=user,password=pw,charset='utf8mb4')


	def insertNewsList(self, url):
		try:
			with self.conn.cursor() as cursor:
				sql = 'INSERT INTO tobigs.news_list (query, start, end, url) VALUES (%s, %s, %s, %s)'
				cursor.execute(sql, (self.myKeyword, self.start, self.end, url))
			self.conn.commit()
		except Exception as e:
			print("DB INSERT ERROR" + e)	


	def insertNews(self, news):
		try:
			with self.conn.cursor() as cursor:
				sql = 'INSERT INTO tobigs.news (url, title, content, date, company) VALUES (%s, %s, %s, %s, %s)'
				cursor.execute(sql, (news['url'], news['title'], news['cont'], news['date'], news['company']))
			self.conn.commit()
		except Exception as e:
			print("DB INSERT ERROR" + e)

	def sqlClose(self):
		print("DB close...")
		if type(self.conn) == pymysql.connections.Connection:
			self.conn.close()
		else:
			print("DB is not connected.") #<class 'pymysql.connections.Connection'>