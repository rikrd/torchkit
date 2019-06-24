#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
Created on Sat Dec 23 01:00:42 2017

@author: chinwei

a simple MADE example
"""



import numpy as np
import torch
import torch.optim as optim
from torch.autograd import Variable
import nn as nn_
import flows
import utils
import matplotlib.pyplot as plt



class density_model(object):
    
    def __init__(self, sampler, n=64, cuda=False):
#        self.mdl = nn_.SequentialFlow( 
#                flows.IAF(2, 64, 1, 2), 
#                flows.FlipFlow(1), 
#                flows.IAF(2, 64, 1, 2),
#                flows.FlipFlow(1), 
#                flows.IAF(2, 64, 1, 2),
#                flows.FlipFlow(1),
#                flows.IAF(2, 64, 1, 2), 
#                flows.FlipFlow(1), 
#                flows.IAF(2, 64, 1, 2),
#                flows.FlipFlow(1), 
#                flows.IAF(2, 64, 1, 2))
        self.mdl = flows.IAF_DDSF(2, 16, 1, 2,
                num_ds_dim=16, num_ds_layers=2)
#        self.mdl = flows.IAF_DSF(2, 64, 1, 3,
#                num_ds_dim=4)
        
        self.optim = optim.Adam(self.mdl.parameters(), lr=0.005, 
                                betas=(0.9, 0.999))
        
        self.sampler = sampler
        self.n = n
        
        self.context = Variable(torch.FloatTensor(n, 1).zero_()) + 2.0
        self.lgd = Variable(torch.FloatTensor(n).zero_())
        self.zeros = Variable(torch.FloatTensor(n, 2).zero_())


        self.gpu = cuda
        if self.gpu:
            self.mdl.cuda()

            self.context = self.context.cuda()
            self.lgd = self.lgd.cuda()
            self.zeros = self.zeros.cuda()


    def density(self, spl, lgd=None, context=None, zeros=None):
        lgd = self.lgd if lgd is None else lgd
        context = self.context if context is None else context
        zeros = self.zeros if zeros is None else zeros

        if self.gpu:
            spl = spl.cuda()
            lgd = lgd.cuda()
            context = context.cuda()
            zeros = zeros.cuda()

        z, logdet, _ = self.mdl((spl, lgd, context))
        losses = - utils.log_normal(z, zeros, zeros+1.0).sum(1) - logdet
        return - losses

        
    def train(self, total=2000):
        
        n = self.n
       
        for it in range(total):

            self.optim.zero_grad()
            
            spl = self.sampler(n)
            
            losses = - self.density(spl)
            
            loss = losses.mean()
            
            loss.backward()
            self.optim.step()
            
            if ((it + 1) % 100) == 0:
                print 'Iteration: [%4d/%4d] loss: %.8f' % \
                    (it+1, total, loss.item())
            
            #self.mdl.made.randomize()


class sampler_model(object):

    def __init__(self, target_energy, batch_size, cuda=False):
        #        self.mdl = nn_.SequentialFlow(
        #                flows.IAF(2, 128, 1, 3),
        #                flows.FlipFlow(1),
        #                flows.IAF(2, 128, 1, 3),
        #                flows.FlipFlow(1),
        #                flows.IAF(2, 128, 1, 3))
        self.mdl = flows.IAF_DSF(2, 64, 1, 4,  # realify=nn_.softplus,
                                 num_ds_dim=5, num_ds_layers=2)

        self.optim = optim.Adam(self.mdl.parameters(), lr=0.0005,
                                betas=(0.9, 0.999))

        self.batch_size = batch_size
        self.target_energy = target_energy

        self.gpu = cuda
        if self.gpu:
            self.mdl.cuda()

    def train(self, total=100):
        for it in range(total):

            self.optim.zero_grad()

            spl, logdet, _ = self.mdl.sample(self.batch_size)

            losses = - self.target_energy(spl) - logdet
            loss = losses.mean()

            loss.backward()
            self.optim.step()

            if ((it + 1) % 100) == 0:
                print 'Iteration: [%4d/%4d] loss: %.8f' % \
                      (it + 1, total, loss.item())


from scipy.stats import multivariate_normal

# build and train
class Mixture:
    """Makes a probabilistic mixture out of any distr_list where distr implements rvs and pdf."""

    def __init__(self, probs, distr_list):
        self.probs = np.asarray(probs)
        self.distr_list = distr_list

    def pdf(self, x):
        pdf = np.asarray([distr.pdf(x) for distr in self.distr_list])
        assert pdf.shape == (len(self.distr_list), len(x))
        return np.dot(self.probs, pdf)

    def rvs(self, n):
        counts = np.random.multinomial(n, self.probs)
        assert np.sum(counts) == n
        assert len(counts == self.probs)
        samples = []
        for k, distr in zip(counts, self.distr_list):
            samples.append(distr.rvs(k))

        samples = np.vstack(samples)
        np.random.shuffle(samples)
        return Variable(torch.from_numpy(samples.astype('float32')))


nmodesperdim = 10
grid = np.linspace(-5,5,nmodesperdim)
grid = np.meshgrid(grid,grid)
grid = np.concatenate([grid[0].reshape(nmodesperdim**2,1),
                       grid[1].reshape(nmodesperdim**2,1)],1)

mix = Mixture(
    np.ones(nmodesperdim**2) / float(nmodesperdim**2),
    [multivariate_normal(mean, 1/float(nmodesperdim*np.log(nmodesperdim))) for mean in grid] )
#mix = Mixture(
#    [0.6, 0.4], 
#    [multivariate_normal((2.0,2.0), 1.0), multivariate_normal((-3.0,-3.0), 0.5)])
# mix = Mixture([0.1, 0.3, 0.4, 0.2], [
#             multivariate_normal([-5., 0]),
#             multivariate_normal([5., 0]),
#             multivariate_normal([0, 5.]),
#             multivariate_normal([0, -5.])])
                    
mdl = density_model(mix.rvs, n=256, cuda=True)
#input('x')
mdl.train(2000)


# plot figure
fig = plt.figure()
n = 200

ax = fig.add_subplot(1,2,1)
x = np.linspace(-10,10,n)
y = np.linspace(-10,10,n)
xx,yy = np.meshgrid(x,y)
X = np.concatenate((xx.reshape(n**2,1),yy.reshape(n**2,1)),1)
X = X.astype('float32')
X = Variable(torch.from_numpy(X))
Z = mix.pdf(X.data.numpy()).reshape(n,n)
ax.pcolormesh(xx,yy,Z)
ax.axis('off')
plt.xlim((-10,10))
plt.ylim((-10,10))


context = Variable(torch.FloatTensor(n**2, 1).zero_()) + 2.0
lgd = Variable(torch.FloatTensor(n**2).zero_())
zeros = Variable(torch.FloatTensor(n**2, 2).zero_())
        

ax = fig.add_subplot(1,2,2)
Z = mdl.density(X, lgd, context, zeros).data.cpu().numpy().reshape(n,n)
ax.pcolormesh(xx,yy,np.exp(Z))
ax.axis('off')
plt.xlim((-10,10))
plt.ylim((-10,10))
#plt.savefig('100MoG.pdf',format='pdf')


smplr = sampler_model(mdl.density, mdl.n, cuda=True)
smplr.train(2000)


from ops import mollify


fig = plt.figure(figsize=(10,15))
for j,mm in enumerate(reversed([0.0,0.2,0.4,0.6,0.8,1.0])):
    mollify(mdl.mdl, mm)
    ax = fig.add_subplot(3,2,j+1)    
    n = 200    
    
    context = Variable(torch.FloatTensor(n**2, 1).zero_()) + 2.0
    lgd = Variable(torch.FloatTensor(n**2).zero_())
    zeros = Variable(torch.FloatTensor(n**2, 2).zero_())
            
    
    Z = mdl.density(X, lgd, context, zeros).data.cpu().numpy().reshape(n,n)
    ax.pcolormesh(xx,yy,np.exp(Z))

    smplr.mdl.eval()
    nspl, logdet, context = smplr.mdl.sample(10000)
    nspl = nspl.detach().cpu().numpy()
    ax.scatter(nspl[:,0], nspl[:,1], s=1, alpha=0.2, c='r')

    ax.axis('off')
    plt.xlim((-10,10))
    plt.ylim((-10,10))


plt.show()


