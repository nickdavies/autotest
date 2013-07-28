
class ImpossibleRestrictionError(Exception):
    pass

class Restriction(object):

    def __init__(self, value):
        self.value = value

    def inverse(self):
        raise NotImplementedError("Not supported for this type")

    def merge(self, r, rev=False):
        '''
        This function is the most complicated for restrictions
        It must take another restriction and return a restriction that
        is the logical equvilent of the two or None if one cannot exist
        '''
        if rev:
            raise NotImplementedError("merge for %s and %s is not defined" % (self.__class__, r.__class__))

        return r.merge(self, True)

    def __str__(self):
        return str(self.value)

class Null(Restriction):
    
    def merge(self, r, rev=False):
        return r

class Equal(Restriction): 
    
    def inverse(self):
        return NotEqual(self.value)

    def merge(self, r, rev=False):
        if isinstance(r, Equal):
            if r.value == self.value:
                return self
            return None

        if isinstance(r, NotEqual):
            if r.value == self.value:
                return None
            return self

        if isinstance(r, NotIn):
            if self.value in r.value:
                return None
            return self

        if isinstance(r, LessThan) or isinstance(r, GreaterThan) or isinstance(r, Between):
            # if equal is in the range then ok
            # otherwise its impossible
            if r.within(self.value):
                return self
            return None

        return super(Equal, self).merge(r, rev)

    def __str__(self):
        return "== %s" % super(Equal, self).__str__()

class NotEqual(Restriction):
    
    def inverse(self):
        return Equal(self.value)

    def merge(self, r, rev=False):
        if isinstance(r, NotEqual):
            if r.value == self.value:
                return self
            return NotIn(set([self.value, r.value]))

        if isinstance(r, NotIn):
            if self.value in r.value:
                return r
            return NotIn(set([self.value]).union(r.value))

        if isinstance(r, LessThan) or isinstance(r, GreaterThan):
            if not r.within(self.value):
                return r

            #TODO: probably a better (less restrictive way)
            return r.__class__(self.value, False)

        if isinstance(r, Between):
            if r.within(self.value):
                if (self.value - r.lt.value) < (self.value - r.gt.value):
                    return Between(r.lt, r.gt.merge(self))
                else:
                    return Between(r.lt.merge(self), r.gt)
            
            return r

        return super(NotEqual, self).merge(r, rev)

    def __str__(self):
        return "!= %s" % super(NotEqual, self).__str__()

class NotIn(Restriction):

    def __str__(self):
        return "not in %s" % super(NotIn, self).__str__()

class Between(Restriction):

    def __init__(self, lt, gt):
        self.lt = lt
        self.gt = gt

        assert lt.value >= gt.value

        if lt.value == gt.value:
            assert lt.eq and gt.eq

    def within(self, value):
        return self.lt.within(value) and self.gt.within(value)

    def __str__(self):
        return str(self.lt) + " and " + str(self.gt)

class LessThan(Restriction):
    
    def __init__(self, value, eq):
        super(LessThan, self).__init__(value)
        self.eq = eq

    def inverse(self):
        return GreaterThan(self.value, not self.eq)

    def within(self, value):
        if self.eq:
            return value <= self.value
        return value < self.value

    def merge(self, r, rev=False):
        if isinstance(r, LessThan):
            if self.value == r.value:
                if not self.eq:
                    return self
                return r
            if self.value < r.value:
                return self
            return r

        if isinstance(r, GreaterThan):
            # 5 < x > 5 OR 5 <= x => 5
            if r.value == self.value:
                if r.eq and self.eq:
                    return Equal(self.value)
                return None

            if r.value < self.value:
                try:
                    return Between(self, r)
                except AssertionError:
                    return None

            return None

        return super(LessThan, self).merge(r, rev)

    def __str__(self):
        if self.eq:
            return "<= %s" % super(LessThan, self).__str__()
        return "< %s" % super(LessThan, self).__str__()

class GreaterThan(Restriction):
    
    def __init__(self, value, eq):
        super(GreaterThan, self).__init__(value)
        self.eq = eq

    def inverse(self):
        return LessThan(self.value, not self.eq)

    def within(self, value):
        if self.eq:
            return value >= self.value
        return value > self.value

    def merge(self, r, rev=False):
        if isinstance(r, GreaterThan):
            if self.value == r.value:
                if not self.eq:
                    return self
                return r
            if self.value > r.value:
                return self
            return r

        return super(GreaterThan, self).merge(r, rev)

    def __str__(self):
        if self.eq:
            return ">= %s" % super(GreaterThan, self).__str__()
        return "> %s" % super(GreaterThan, self).__str__()


