import sys
import ast
import _ast
import inspect

import test_file

################# OBJECTS

class Argument(object):

    def __init__(self, name):
        self.name = name

    def satisfy(self, restrictions):
        raise NotImplementedError("Must overwrite in child class")

    def __str__(self):
        return self.name

class Number(Argument):

    def satisfy(self, restrictions):
        final_r = Null(None)
        for r in restrictions:
            final_r = final_r.merge(r)
            if final_r is None:
                raise ValueError("Cannot satisfy restrictions: %s" % " and ".join((str(a) for a in restrictions)))

        if isinstance(final_r, Null):
            return 0

        if isinstance(final_r, Equal):
            return final_r.value

        if isinstance(final_r, NotEqual):
            return final_r.value + 1

        if isinstance(final_r, NotIn):
            i = 1
            while i in final_r.value:
                i += 1
            return i

        raise NotImplementedError("Cannot satisfy restrictions: %s" % final_r)

    def __str__(self):
        return "Num(%s)" % super(Number, self).__str__()

class String(Argument):
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


        return super(NotEqual, self).merge(r, rev)

    def __str__(self):
        return "!= %s" % super(NotEqual, self).__str__()

class NotIn(Restriction):

    def __str__(self):
        return "not in %s" % super(NotIn, self).__str__()

class ArgumentRestrictions(object):

    def __init__(self, arg, restrictions):
        self.arg = arg
        self.restrictions = restrictions

    def satisfy(self):
        return self.arg, self.arg.satisfy(self.restrictions)

    def extend(self, restrictions):
        return ArgumentRestrictions(self.arg, self.restrictions + restrictions.restrictions)

    def __str__(self):
        return " and ".join((str(self.arg) + " " + str(r) for r in self.restrictions))

def get_arg_type(name):
    if name == "a":
        return Number

    if name == "b":
        return Number

class Stmt(object):

    @classmethod
    def split_equals(cls, left, right):
        
        if isinstance(left, _ast.Name) and isinstance(right, _ast.Num):
            arg = Number(left.id)
            rest = Equal(right.n)
            return ArgumentRestrictions(arg, [rest]), ArgumentRestrictions(arg, [rest.inverse()]),

    @classmethod
    def split_compare(cls, compare):
        if len(compare.ops) > 1 or len(compare.comparators) > 1:
            raise NotImplementedError("Multiple operations in compare not supported")

        left = compare.left
        op = compare.ops[0]
        right = compare.comparators[0]

        if isinstance(op, _ast.Eq):
           return cls.split_equals(left, right) 
        else:
            raise NotImplementedError("Operator not supported: %s" % op)

        raise NotImplementedError("Some unsupported operation occured!")


class Branch(object):

    @classmethod
    def is_terminal(cls, ast_branch):
        for stmt in ast_branch:
            if isinstance(stmt, _ast.If):
                return cls.is_terminal(stmt.body)
            if isinstance(stmt, _ast.Return):
                return True
            if isinstance(stmt, _ast.Assign):
                return False

            print >> sys.stderr, "Unknown stmt in is_terminal", stmt

    def __init__(self, body, restrictions):
        self.body = body
        self.restrictions = restrictions

class Decision(object):
    
    def __init__(self, ast_if, body):
        self.ast_if = ast_if
        self.body = body
        self.children = None

        if ast_if is not None:
            test = ast_if.test
            if isinstance(test, _ast.Compare):
                r_t, r_f = Stmt.split_compare(test)

                self.r_t = r_t
                self.r_f = r_f
            else:
                raise NotImplementedError("Unknown _ast.If.test value: %s" % test)

    def load_children(self, parent_next=None):
        children = []
        for stmt in self.body:
            if isinstance(stmt, _ast.If):
                test = stmt.test
                body = stmt.body

                children.append(Decision(stmt, stmt.body))

            elif isinstance(stmt, _ast.Return):
                break
            elif isinstance(stmt, _ast.Raise):
                break

        for i in xrange(len(children)):
            my_next = parent_next
            if i != len(children) - 1:
                my_next = children[i + 1]

            child_count = children[i].load_children(my_next)
            if child_count != 0:
                children[i].set_true_next(children[i].children[0])
            else:
                children[i].set_true_next(my_next)

            children[i].set_false_next(my_next)

            #print children[i], "t_next =", children[i].n_t, "f_next =", children[i].n_t

        self.children = children
        return len(children)

    def set_true_next(self, n):
        self.n_t = n

    def set_false_next(self, n):
        self.n_f = n

    def gen_tests(self, restrictions, path=[]):
        #print "Visiting:", self, "via:", path

        r_t = restrictions.extend(self.r_t)
        r_f = restrictions.extend(self.r_f)

        path_t = path + [(self, True)]
        path_f = path + [(self, False)]

        # go into IF
        if self.n_t is not None:
            for test in self.n_t.gen_tests(r_t, path_t):
                yield test
        else: 
            yield r_t, path_t

        # dont go into IF
        if self.n_f is not None:
            for test in self.n_t.gen_tests(r_f, path_f):
                yield test
        else: 
            yield r_f, path_f

    def __str__(self):
        return "D%s" % self.ast_if.test.comparators[0].n
        #return "Decision %s@%x r_t=%s, r_f=%s" % (self.ast_if.test.comparators[0].n, id(self), self.r_t, self.r_f)

class Func(object):

    @classmethod
    def load_f(cls, f):
        tree = ast.parse(inspect.getsource(f))

        f_tree = tree.body[0]
        assert isinstance(f_tree, _ast.FunctionDef)
        return f_tree

    @classmethod
    def load_args(cls, f_tree):
        args = []
        for arg in f_tree.args.args:
            args.append(get_arg_type(arg.id)(arg.id))
        return args

    def gen_test_cases(self):
        for r, path in self.root_decision.children[0].gen_tests(ArgumentRestrictions(Number("a"), [])):
            try:
                arg, value = r.satisfy()
                yield arg, value
                print >> sys.stderr, arg.name, "==", value
            except ValueError as e:
                print >> sys.stderr,  e

    def __init__(self, f, module=None):
        self.f = f
        self.module = module
        if module is None and f.__module__ != "__main__":
                self.module = f.__module__

        if self.module is not None:
            self.name = self.module + "." + f.func_name

        self.tree = self.load_f(f)
        self.args = self.load_args(self.tree)

        self.root_decision = Decision(None, self.tree.body)
        self.root_decision.load_children(None)

        success = ""
        errors = ""
        for arg, value in self.gen_test_cases():
            try:
                result = self.f(value)
                success += "assert %s(%s) == %s\n" % (self.name, value, result)
            except Exception as e:
                e_name = str(e.__class__.__name__)
                errors += "try:\n"
                errors += "    %s(%s)\n" % (self.name, value)
                errors += "    assert False, 'Did not raise %s'\n" % e_name
                errors += "except %s:\n" % e_name
                errors += "     pass\n\n"

        if self.module is not None:
            print "import ", self.module
        print
        print success
        print errors

        #print self.f, self.name, self.tree, self.args

f = Func(test_file.lol)
