print("Hello World")

t = (10,20,5,20,30,0)
print(t, 30 in t, t.index(30), t.count(20), len(t), sorted(t, reverse=True), any(t), all(t))
print(t+(40,))
print("-------------END------------")

s = set([])
print(s)
s.add(10)
s.add(20)
s.add(23)
s.update([40,44])
print(s)